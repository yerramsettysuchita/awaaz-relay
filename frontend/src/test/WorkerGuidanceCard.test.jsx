import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import WorkerGuidanceCard from "../components/WorkerGuidanceCard";

const SAMPLE_GUIDANCE = [
  "Confirm the applicant is a widow with a death certificate.",
  "Verify annual income is below Rs 2.4 lakhs.",
  "Collect FORM 1-W from the BDO office.",
];

describe("WorkerGuidanceCard", () => {
  it("renders all guidance items", () => {
    render(<WorkerGuidanceCard guidance={SAMPLE_GUIDANCE} domain="pension_eligibility" />);
    SAMPLE_GUIDANCE.forEach((item) => {
      expect(screen.getByText(item)).toBeInTheDocument();
    });
  });

  it("shows correct domain label", () => {
    render(<WorkerGuidanceCard guidance={SAMPLE_GUIDANCE} domain="pension_eligibility" />);
    expect(screen.getByText("Pension Eligibility")).toBeInTheDocument();
  });

  it("shows 0/3 progress initially", () => {
    render(<WorkerGuidanceCard guidance={SAMPLE_GUIDANCE} domain="process" />);
    expect(screen.getByText("0 / 3 steps done")).toBeInTheDocument();
  });

  it("updates progress when checkbox is clicked", () => {
    render(<WorkerGuidanceCard guidance={SAMPLE_GUIDANCE} domain="process" />);
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    expect(screen.getByText("1 / 3 steps done")).toBeInTheDocument();
  });

  it("shows completion message when all items checked", () => {
    render(<WorkerGuidanceCard guidance={SAMPLE_GUIDANCE} domain="process" />);
    screen.getAllByRole("checkbox").forEach((cb) => fireEvent.click(cb));
    expect(screen.getByText(/All steps completed/i)).toBeInTheDocument();
  });

  it("shows escalation banner when escalation needed", () => {
    render(
      <WorkerGuidanceCard
        guidance={SAMPLE_GUIDANCE}
        domain="out_of_scope"
        escalationNeeded={true}
        escalationReason="Query involves medical condition."
      />
    );
    expect(screen.getByText(/Escalation required/i)).toBeInTheDocument();
    expect(screen.getByText(/Query involves medical condition/i)).toBeInTheDocument();
  });

  it("does not show escalation banner when not needed", () => {
    render(
      <WorkerGuidanceCard
        guidance={SAMPLE_GUIDANCE}
        domain="pension_eligibility"
        escalationNeeded={false}
      />
    );
    expect(screen.queryByText(/Escalation required/i)).not.toBeInTheDocument();
  });
});
