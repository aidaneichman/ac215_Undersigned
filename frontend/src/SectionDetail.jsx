// The panel for the section picked in the table. Titles repeat across the rule (every part of
// III has a "1. What are the agencies proposing?"), so it leads with the full heading path.

function count(value) {
  return value === null ? <span className="muted">not counted yet</span> : value.toLocaleString("en-US");
}

export default function SectionDetail({ section, onClose }) {
  const path = section.heading.split(" > ");
  return (
    <aside className="detail" aria-label="Section details">
      <button type="button" className="close" onClick={onClose} aria-label="Close details">
        ×
      </button>
      <ol className="path">
        {path.map((part, i) => (
          <li key={i} className={i === path.length - 1 ? "here" : undefined}>
            {part}
          </li>
        ))}
      </ol>
      <dl className="facts">
        <dt>Rule</dt>
        <dd>
          <a href={`https://www.federalregister.gov/d/${section.document_number}`} target="_blank" rel="noreferrer">
            {section.citation}
          </a>
          {section.page !== null && `, page ${section.page}`}
        </dd>
        <dt>Rule passages</dt>
        <dd>{count(section.rule_passages)}</dd>
        <dt>Citing passages</dt>
        <dd>{count(section.citing_passages)}</dd>
        <dt>Citing letters</dt>
        <dd>{count(section.citing_letters)}</dd>
      </dl>
      <h2>Comment passages that cite this section</h2>
      {/* The API has no endpoint for these yet. It comes once the passage stage links comment
          passages to sections; this panel will then fetch and list them here. */}
      <p className="muted">
        Not available yet. They will be listed here once comment letters are split into passages
        and linked to the sections they cite.
      </p>
    </aside>
  );
}
