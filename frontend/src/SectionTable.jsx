// One row per section from GET /rules/{docket}/sections, in reading order. Parent rows come
// before their children, so indenting by depth is enough to show the tree.

// The API sends null for counts it has no data for yet (citing passages and letters, until
// comment passages are linked to sections). Null is unknown, not zero, so it is not shown as 0.
function count(value) {
  return value === null ? <span className="muted">—</span> : value.toLocaleString("en-US");
}

export default function SectionTable({ sections }) {
  const unknown = sections.some((s) => s.citing_passages === null);
  return (
    <>
      <table className="sections">
        <thead>
          <tr>
            <th>Section</th>
            <th className="n">FR page</th>
            <th className="n">Rule passages</th>
            <th className="n">Citing passages</th>
            <th className="n">Citing letters</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((s) => (
            <tr key={`${s.document_number}/${s.section_ref}`} className={`depth-${s.depth}`}>
              <td>
                <span className="title" style={{ marginLeft: `${(s.depth - 1) * 1.25}rem` }}>{s.title}</span>
              </td>
              <td className="n">{s.page ?? count(null)}</td>
              <td className="n">{count(s.rule_passages)}</td>
              <td className="n">{count(s.citing_passages)}</td>
              <td className="n">{count(s.citing_letters)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {unknown && (
        <p className="foot">
          — means not counted yet. Citing counts appear once comment passages are linked to the
          sections they cite.
        </p>
      )}
    </>
  );
}
