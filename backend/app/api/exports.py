import csv
import io
import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.discovery import DiscoveryJob, DiscoveryResult
from app.models.profile import CandidateProfile
from app.models.user import User
from app.services.audit import record_audit_log

router = APIRouter(prefix="/discovery", tags=["Exports"])


def _load_export_rows(db: Session, job_id: UUID, current_user: User) -> tuple[DiscoveryJob, list[dict]]:
    job = (
        db.query(DiscoveryJob)
        .filter(DiscoveryJob.id == job_id, DiscoveryJob.owner_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery job not found")

    results = (
        db.query(DiscoveryResult)
        .options(
            joinedload(DiscoveryResult.ranking_score),
            joinedload(DiscoveryResult.explanation),
        )
        .filter(DiscoveryResult.discovery_job_id == job.id)
        .order_by(DiscoveryResult.rank_position.asc())
        .all()
    )
    cand_ids = [r.candidate_id for r in results]
    cand_map = (
        {c.id: c for c in db.query(CandidateProfile).filter(CandidateProfile.id.in_(cand_ids)).all()}
        if cand_ids
        else {}
    )

    export_rows: list[dict] = []
    for r in results:
        c = cand_map.get(r.candidate_id)
        if not c:
            continue
        rs = r.ranking_score
        ex = r.explanation
        export_rows.append({
            "rank": r.rank_position,
            "candidate_id": str(c.id),
            "full_name": c.full_name,
            "current_role": c.current_role or "",
            "organization": c.organization_name or "",
            "location": c.location or "",
            "experience_years": c.experience_years if c.experience_years is not None else "",
            "linkedin_url": c.linkedin_url or "",
            "relevance_score": r.relevance_score,
            "evidence_confidence": r.evidence_confidence,
            "meets_minimum_evidence": r.meets_minimum_evidence,
            "relevance_tier": r.relevance_tier,
            "semantic_similarity": rs.semantic_similarity if rs else 0.0,
            "school_ecosystem_relevance": rs.school_ecosystem_relevance if rs else 0.0,
            "professional_role_similarity": rs.professional_role_similarity if rs else 0.0,
            "experience_similarity": rs.experience_similarity if rs else 0.0,
            "organization_network_overlap": rs.organization_network_overlap if rs else 0.0,
            "influence_indicators_score": rs.influence_indicators_score if rs else 0.0,
            "school_indicators": "; ".join(c.school_indicators or []),
            "verification_status": c.verification_status,
            "dataset_type": c.dataset_type,
            "data_source": c.primary_source,
            "source_record_id": c.source_record_id,
            "source_url": c.source_url or "",
            "usage_restrictions": c.usage_restrictions,
            "explanation": ex.summary_explanation if ex else "",
            "last_updated": c.last_updated.isoformat(),
        })
    return job, export_rows


@router.get("/{job_id}/export/csv")
def export_csv(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job, rows = _load_export_rows(db, job_id, current_user)
    buf = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else [
        "rank", "candidate_id", "full_name", "current_role", "organization",
        "relevance_score", "evidence_confidence", "verification_status", "data_source",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    record_audit_log(
        db,
        action="DISCOVERY_EXPORTED_CSV",
        resource_type="discovery_job",
        resource_id=str(job.id),
        user_id=current_user.id,
        details={"row_count": len(rows)},
    )
    db.commit()

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="educonnect_discovery_{job.id}.csv"'},
    )


@router.get("/{job_id}/export/xlsx")
def export_xlsx(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job, rows = _load_export_rows(db, job_id, current_user)
    wb = Workbook()
    ws = wb.active
    ws.title = "Discovery Results"

    headers = list(rows[0].keys()) if rows else [
        "rank", "full_name", "current_role", "organization", "relevance_score",
        "evidence_confidence", "verification_status", "data_source",
    ]
    ws.append(headers)
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    ws_meta = wb.create_sheet(title="Provenance & Model Info")
    ws_meta.append(["Job ID", str(job.id)])
    ws_meta.append(["Discovery Mode", job.discovery_mode])
    ws_meta.append(["Exported At", datetime.now(timezone.utc).isoformat()])
    ws_meta.append(["Ranking Model Version", job.ranking_model_version])
    ws_meta.append(["Embedding Model", job.embedding_model_name])
    ws_meta.append(["Total Evaluated", job.total_candidates_evaluated])
    ws_meta.append(["Relevant Discovered", job.relevant_candidates_count])
    ws_meta.append(["Weights", json.dumps(job.weights_snapshot)])

    out_stream = io.BytesIO()
    wb.save(out_stream)
    out_stream.seek(0)

    record_audit_log(
        db,
        action="DISCOVERY_EXPORTED_XLSX",
        resource_type="discovery_job",
        resource_id=str(job.id),
        user_id=current_user.id,
        details={"row_count": len(rows)},
    )
    db.commit()

    return StreamingResponse(
        out_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="educonnect_discovery_{job.id}.xlsx"'},
    )


@router.get("/{job_id}/export/json")
def export_json(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job, rows = _load_export_rows(db, job_id, current_user)
    payload = {
        "discovery_job_id": str(job.id),
        "discovery_mode": job.discovery_mode,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "ranking_model_version": job.ranking_model_version,
        "embedding_model_name": job.embedding_model_name,
        "weights_snapshot": job.weights_snapshot,
        "total_candidates": len(rows),
        "results": rows,
    }
    record_audit_log(
        db,
        action="DISCOVERY_EXPORTED_JSON",
        resource_type="discovery_job",
        resource_id=str(job.id),
        user_id=current_user.id,
        details={"row_count": len(rows)},
    )
    db.commit()

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="educonnect_discovery_{job.id}.json"'},
    )
