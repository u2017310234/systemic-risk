import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6 text-center">
      <p className="font-mono text-sm uppercase tracking-[0.3em] text-muted">Not found</p>
      <h1 className="mt-4 font-display text-4xl">The requested bank or page does not exist.</h1>
      <Link
        href="/"
        className="mt-8 rounded-full border border-line bg-panel px-5 py-3 text-sm text-text transition hover:border-accent"
      >
        Return to dashboard
      </Link>
    </main>
  );
}
