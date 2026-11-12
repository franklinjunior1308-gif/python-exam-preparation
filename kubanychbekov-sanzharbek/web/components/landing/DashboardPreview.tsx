import { LogoMark } from "./icons";

const MENU = ["Dashboard", "Requests", "Dispatch", "Assets", "Technicians", "Analytics", "Settings"];

const STATS = [
  { value: "128", label: "Open requests" },
  { value: "96%", label: "On-track SLA" },
  { value: "87%", label: "First-visit fix" },
  { value: "2.6 h", label: "Avg. response" },
];

const ROWS = [
  { id: "REQ-7843", title: "HVAC maintenance", status: "In progress" },
  { id: "REQ-7844", title: "Pump not starting", status: "Scheduled" },
  { id: "REQ-7845", title: "Routine inspection", status: "Accepted" },
  { id: "REQ-7846", title: "Leak repair (Site B)", status: "Submitted" },
];

const SCHEDULE = [
  { name: "Alex M.", id: "REQ-7843", left: 8, width: 44, color: "#2563eb" },
  { name: "Taylor R.", id: "REQ-7845", left: 36, width: 50, color: "#7c3aed" },
  { name: "Jordan K.", id: "REQ-7844", left: 28, width: 40, color: "#0891b2" },
];

const LEGEND = [
  { label: "In progress", value: "34%", color: "#38bdf8" },
  { label: "Scheduled", value: "28%", color: "#818cf8" },
  { label: "Accepted", value: "20%", color: "#6366f1" },
  { label: "Submitted", value: "12%", color: "#94a3b8" },
  { label: "Completed", value: "6%", color: "#34d399" },
];

export function DashboardPreview() {
  // Decorative mock-up: hidden from assistive technology, the caption below explains it.
  return (
    <div className="pv" aria-hidden="true">
      <aside className="pv-side">
        <div className="pv-brand">
          <LogoMark size={22} /> FixFlow
        </div>
        {MENU.map((item, index) => (
          <div key={item} className={index === 0 ? "pv-item active" : "pv-item"}>
            {item}
          </div>
        ))}
      </aside>

      <div className="pv-main">
        <div className="pv-top">
          <div>
            <strong>Good morning, Operations Team</strong>
            <small>Here&apos;s what&apos;s happening in the field today.</small>
          </div>
        </div>

        <div className="pv-stats">
          {STATS.map((stat) => (
            <div key={stat.label} className="pv-stat">
              <b>{stat.value}</b>
              <small>{stat.label}</small>
            </div>
          ))}
        </div>

        <div className="pv-grid">
          <div className="pv-card">
            <h4>Requests</h4>
            {ROWS.map((row) => (
              <div key={row.id} className="pv-row">
                <span>{row.id}</span>
                <span>{row.title}</span>
                <em>{row.status}</em>
              </div>
            ))}
          </div>

          <div className="pv-card pv-hide-sm">
            <h4>Technician schedule</h4>
            {SCHEDULE.map((item) => (
              <div key={item.id} className="pv-gantt">
                <span>{item.name}</span>
                <div className="pv-track">
                  <i
                    style={{
                      left: `${item.left}%`,
                      width: `${item.width}%`,
                      background: item.color,
                    }}
                  >
                    {item.id}
                  </i>
                </div>
              </div>
            ))}
          </div>

          <div className="pv-card pv-hide-sm">
            <h4>Request status</h4>
            <div className="pv-donut-row">
              <div className="pv-donut">
                <span>
                  128
                  <small>Total</small>
                </span>
              </div>
              <ul>
                {LEGEND.map((item) => (
                  <li key={item.label}>
                    <i style={{ background: item.color }} /> {item.label} <b>{item.value}</b>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="pv-card pv-hide-sm">
            <h4>Asset health</h4>
            <b className="pv-big">96%</b>
            <small>Asset uptime</small>
            <svg viewBox="0 0 200 60" className="pv-chart" focusable="false">
              <polyline
                points="0,45 25,38 50,42 80,30 110,34 140,22 170,26 200,10"
                fill="none"
                stroke="#22d3ee"
                strokeWidth="2.5"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
