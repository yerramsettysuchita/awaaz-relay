import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import EscalationCard from "../components/EscalationCard";

describe("EscalationCard", () => {
  it("renders default reason when none provided", () => {
    render(<EscalationCard />);
    expect(screen.getByText(/human officer to review/i)).toBeInTheDocument();
  });

  it("renders custom escalation reason", () => {
    render(<EscalationCard reason="Query involves medical condition outside pension scope." />);
    expect(screen.getByText("Query involves medical condition outside pension scope.")).toBeInTheDocument();
  });

  it("shows helpline number", () => {
    render(<EscalationCard />);
    expect(screen.getByText(/1800-425-1700/i)).toBeInTheDocument();
  });

  it("shows BDO office contact", () => {
    render(<EscalationCard />);
    expect(screen.getByText(/Block Development Office/i)).toBeInTheDocument();
  });

  it("renders Aadhaar helpline link", () => {
    render(<EscalationCard />);
    expect(screen.getByText(/1947/i)).toBeInTheDocument();
  });
});
