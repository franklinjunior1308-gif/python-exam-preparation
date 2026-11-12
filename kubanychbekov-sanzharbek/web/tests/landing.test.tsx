import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import HomePage from "@/app/page";

const html = renderToStaticMarkup(<HomePage />);

describe("landing page", () => {
  test("shows the headline", () => {
    expect(html).toContain("Streamline Field Service");
    expect(html).toContain("Operations");
  });

  test("links the call-to-action buttons to the login page", () => {
    const loginLinks = html.match(/href="\/login"/g) ?? [];
    expect(loginLinks.length).toBeGreaterThanOrEqual(3);
  });

  test("lists all four feature cards", () => {
    for (const title of [
      "Dispatching",
      "Asset Management",
      "Technician Mobile App",
      "SLA Tracking",
    ]) {
      expect(html).toContain(title);
    }
  });

  test("labels the dashboard mock-up as sample data", () => {
    expect(html).toContain("Illustrative preview with sample data");
  });

  test("has a skip link and a main landmark", () => {
    expect(html).toContain('href="#main"');
    expect(html).toContain('<main id="main">');
  });
});
