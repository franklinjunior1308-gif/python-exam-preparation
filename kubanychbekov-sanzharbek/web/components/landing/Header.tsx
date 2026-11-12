import Link from "next/link";
import { LogoMark } from "./icons";

const NAV = [
  { href: "#features", label: "Features" },
  { href: "#preview", label: "Preview" },
  { href: "#highlights", label: "Why FixFlow" },
];

export function Header() {
  return (
    <header className="site-header">
      <div className="container header-row">
        <Link href="/" className="brand" aria-label="FixFlow home">
          <LogoMark />
          <span>FixFlow</span>
        </Link>

        <nav aria-label="Main" className="nav-desktop">
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="header-actions">
          <Link href="/login" className="btn btn-outline">
            Login
          </Link>
          <Link href="/login" className="btn btn-primary">
            Get Started
          </Link>
        </div>
      </div>

      <details className="nav-mobile">
        <summary>Menu</summary>
        <nav aria-label="Mobile">
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
      </details>
    </header>
  );
}
