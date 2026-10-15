import { useEffect, useState } from "react";

import { getJson } from "./api.js";

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getJson("/health").then(setHealth, setError);
  }, []);

  return (
    <>
      <header className="bar">
        <span className="brand">UNDERSIGNED</span>
        <span className="crumb">Rule page</span>
      </header>
      <main className="card">
        {error && <p className="error">{error.message}</p>}
        {!error && !health && <p className="muted">Connecting to the API…</p>}
        {health && (
          <p>
            API {health.status}: {health.passages} rule passages for {health.dockets.join(", ")}
          </p>
        )}
      </main>
    </>
  );
}
