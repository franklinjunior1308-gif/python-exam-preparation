const HIGHLIGHTS = [
  { title: "Multi-tenant", text: "Organizations are fully isolated from each other" },
  { title: "Offline-first", text: "Technician notes and photos queue up and sync later" },
  { title: "SLA-aware", text: "Deadlines count working hours, holidays and estimate pauses" },
  { title: "Audited", text: "Every state change is recorded with who and when" },
];

export function Highlights() {
  return (
    <section id="highlights" className="highlights container" aria-label="Why FixFlow">
      <ul>
        {HIGHLIGHTS.map((item) => (
          <li key={item.title}>
            <strong>{item.title}</strong>
            <span>{item.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
