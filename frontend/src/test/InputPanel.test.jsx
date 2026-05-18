import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import InputPanel from "../components/InputPanel";

// Mock SpeechRecognition (not available in jsdom)
global.SpeechRecognition = undefined;
global.webkitSpeechRecognition = undefined;

describe("InputPanel", () => {
  it("renders submit button disabled initially (no text)", () => {
    render(<InputPanel onSubmit={vi.fn()} loading={false} />);
    expect(screen.getByRole("button", { name: /Analyse/i })).toBeDisabled();
  });

  it("enables submit after typing text", () => {
    render(<InputPanel onSubmit={vi.fn()} loading={false} />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Am I eligible for widow pension?" } });
    expect(screen.getByRole("button", { name: /Analyse/i })).not.toBeDisabled();
  });

  it("fills textarea when a quick query chip is clicked", () => {
    render(<InputPanel onSubmit={vi.fn()} loading={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Am I eligible?" }));
    const textarea = screen.getByRole("textbox");
    expect(textarea.value).toContain("widow");
  });

  it("calls onSubmit with FormData on submit", () => {
    const mockSubmit = vi.fn();
    render(<InputPanel onSubmit={mockSubmit} loading={false} />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Test query" } });
    fireEvent.click(screen.getByRole("button", { name: /Analyse/i }));
    expect(mockSubmit).toHaveBeenCalledOnce();
    expect(mockSubmit.mock.calls[0][0]).toBeInstanceOf(FormData);
  });

  it("keeps submit disabled while loading", () => {
    render(<InputPanel onSubmit={vi.fn()} loading={true} />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Test query" } });
    expect(screen.getByRole("button", { name: /Analys/i })).toBeDisabled();
  });
});
