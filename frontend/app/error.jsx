"use client";

import { safeErrorMessage } from "../src/lib/safe-error-message.js";

export default function ErrorPage({ error, reset }) {
  return (
    <main className="container error-page" role="alert">
      <h1>GitHub data could not be loaded</h1>
      <p>{safeErrorMessage(error)}</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}
