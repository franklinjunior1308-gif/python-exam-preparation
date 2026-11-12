import Link from "next/link";
import { DashboardPreview } from "./DashboardPreview";
import { ArrowIcon, BoltIcon, CheckIcon, PlayIcon } from "./icons";

const POINTS = ["Real-time dispatching", "Offline-ready technician app", "Working-hours SLA tracking"];

export function Hero() {
  return (
    <section className="hero container" aria-labelledby="hero-title">
      <div className="hero-copy">
        <span className="badge">
          <BoltIcon size={16} /> Field Service Management Platform
        </span>
        <h1 id="hero-title">
          Streamline Field Service <span className="accent">Operations</span>
        </h1>
        <p className="lead">
          A complete field service management platform to dispatch work, manage maintenance, handle
          service requests, coordinate technicians and keep every commitment on track, all in one
          place.
        </p>
        <div className="cta-row">
          <Link href="/login" className="btn btn-primary btn-lg">
            Get Started <ArrowIcon size={18} />
          </Link>
          <a href="#preview" className="btn btn-outline btn-lg">
            <PlayIcon size={16} /> View Preview
          </a>
        </div>
        <ul className="checks">
          {POINTS.map((point) => (
            <li key={point}>
              <CheckIcon size={18} /> {point}
            </li>
          ))}
        </ul>
      </div>

      <div id="preview" className="hero-visual">
        <DashboardPreview />
        <p className="caption">Illustrative preview with sample data.</p>
      </div>
    </section>
  );
}
