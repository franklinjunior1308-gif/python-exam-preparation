import Link from "next/link";
import { LogoMark } from "./icons";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <Link href="/" className="brand" aria-label="FixFlow home">
          <LogoMark size={28} />
          <span>FixFlow</span>
        </Link>
        <p>Field Service Management for Modern Operations</p>
        <nav aria-label="Footer">
          <a href="#features">Features</a>
          <a href="#highlights">Why FixFlow</a>
          <Link href="/login">Login</Link>
        </nav>
      </div>
    </footer>
  );
}
