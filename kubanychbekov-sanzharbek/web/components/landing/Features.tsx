import type { ReactNode } from "react";
import { LayersIcon, PhoneIcon, ShieldIcon, TruckIcon } from "./icons";

type Feature = { title: string; text: string; icon: ReactNode };

const FEATURES: Feature[] = [
  {
    title: "Dispatching",
    text: "Assign the right work to the right technician, with skills, availability and conflict checks.",
    icon: <TruckIcon size={30} />,
  },
  {
    title: "Asset Management",
    text: "Track equipment, service history and planned maintenance for every site.",
    icon: <LayersIcon size={30} />,
  },
  {
    title: "Technician Mobile App",
    text: "Tasks, notes, photos and materials on Android, with offline queueing and later sync.",
    icon: <PhoneIcon size={30} />,
  },
  {
    title: "SLA Tracking",
    text: "Working-hours deadlines, risk indicators and one-time escalation of overdue requests.",
    icon: <ShieldIcon size={30} />,
  },
];

export function Features() {
  return (
    <section id="features" className="features container" aria-labelledby="features-title">
      <h2 id="features-title">
        Everything You Need to Run a <span className="accent">Smarter Field Service Operation</span>
      </h2>
      <p className="sub">Powerful, connected tools for modern field service teams.</p>

      <ul className="feature-grid">
        {FEATURES.map((feature) => (
          <li key={feature.title} className="feature-card">
            <span className="feature-icon">{feature.icon}</span>
            <div>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
