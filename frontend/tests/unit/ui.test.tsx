import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import {
  Alert,
  ClassificationBadge,
  DatasetEnvironmentBadge,
  ScoreBar,
  VerificationBadge,
} from "@/components/ui/primitives";

describe("EduConnect UI Primitives", () => {
  it("renders distinct verified vs unverified real badges with no synthetic badges", () => {
    const { rerender } = render(<VerificationBadge status="verified" />);
    expect(screen.getByText("VERIFIED REAL")).toBeInTheDocument();

    rerender(<VerificationBadge status="unverified" />);
    expect(screen.getByText("UNVERIFIED REAL")).toBeInTheDocument();
  });

  it("renders attribute classification provenance labels", () => {
    const { rerender } = render(<ClassificationBadge type="OBSERVED_FACT" />);
    expect(screen.getByText("OBSERVED FACT")).toBeInTheDocument();

    rerender(<ClassificationBadge type="SOURCE_SUPPORTED" />);
    expect(screen.getByText("SOURCE-SUPPORTED FACT")).toBeInTheDocument();

    rerender(<ClassificationBadge type="AI_DERIVED" />);
    expect(screen.getByText("AI-DERIVED CLASSIFICATION")).toBeInTheDocument();

    rerender(<ClassificationBadge type="MISSING_INFORMATION" />);
    expect(screen.getByText("MISSING INFORMATION")).toBeInTheDocument();
  });

  it("renders real data environment badges", () => {
    const { rerender } = render(<DatasetEnvironmentBadge datasetType="REAL_DATA" />);
    expect(screen.getByText("REAL EXTERNAL SOURCE")).toBeInTheDocument();

    rerender(<DatasetEnvironmentBadge datasetType="USER_PROVIDED" />);
    expect(screen.getByText("AUTHORIZED UPLOAD")).toBeInTheDocument();

    rerender(<DatasetEnvironmentBadge datasetType="ALL_AUTHORIZED" />);
    expect(screen.getByText("ALL AUTHORIZED SOURCES")).toBeInTheDocument();
  });

  it("renders ScoreBar and accessible Alert regions", () => {
    render(
      <div>
        <ScoreBar label="Semantic Similarity" value={84.5} />
        <Alert tone="error" title="Validation Error">
          Missing bio field
        </Alert>
      </div>
    );
    expect(screen.getByText("Semantic Similarity")).toBeInTheDocument();
    expect(screen.getByText("84.5")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Missing bio field");
  });
});
