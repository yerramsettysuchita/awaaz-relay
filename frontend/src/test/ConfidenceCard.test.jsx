import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ConfidenceCard from "../components/ConfidenceCard";

describe("ConfidenceCard", () => {
  it("renders high confidence band with correct label and percent", () => {
    render(<ConfidenceCard band="high" percent={85} processingMs={200} />);
    expect(screen.getByText("High Confidence")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("renders medium confidence band", () => {
    render(<ConfidenceCard band="medium" percent={55} />);
    expect(screen.getByText("Medium Confidence")).toBeInTheDocument();
    expect(screen.getByText("55%")).toBeInTheDocument();
  });

  it("renders low confidence band with escalation message", () => {
    render(<ConfidenceCard band="low" percent={20} />);
    expect(screen.getByText("Low Confidence")).toBeInTheDocument();
    expect(screen.getByText(/speak directly to a human officer/i)).toBeInTheDocument();
  });

  it("shows processing time when provided", () => {
    render(<ConfidenceCard band="high" percent={90} processingMs={350} />);
    expect(screen.getByText("⚡ 350ms")).toBeInTheDocument();
  });

  it("falls back to low config for unknown band", () => {
    render(<ConfidenceCard band="unknown" percent={0} />);
    expect(screen.getByText("Low Confidence")).toBeInTheDocument();
  });
});
