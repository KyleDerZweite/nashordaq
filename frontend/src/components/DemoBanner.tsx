export default function DemoBanner() {
  return (
    <div className="mb-4 border-b border-hex-gold bg-hex-panel px-4 py-2 text-center font-mono text-xs text-hex-bronze">
      Demo trades use your own temporary portfolio. Sign out to delete it.
      Sessions expire after 30 minutes without interaction. Closing a browser
      does not delete your state immediately.
    </div>
  );
}
