import Header from "../src/components/layout/Header";

export default function NotFound() {
  return (
    <>
      <Header />
      <main className="container error-page">
        <h1>GitHub page not found</h1>
        <p>The requested public user or repository could not be found.</p>
        <a href="/">Return to GitScope</a>
      </main>
    </>
  );
}
