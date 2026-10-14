import { useState } from "react";
import type { ReactNode } from "react";

export default function SecretLinkDelivery({
  id,
  label,
  url,
  copyLabel,
  copySuccess,
  buttonClass,
  children,
}: {
  id: string;
  label: string;
  url: string;
  copyLabel: string;
  copySuccess: string;
  buttonClass: string;
  children: ReactNode;
}) {
  const [copyMessage, setCopyMessage] = useState<string>();

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopyMessage(copySuccess);
    } catch {
      setCopyMessage(
        "Select and copy the link above. Clipboard access is unavailable.",
      );
    }
  }

  return (
    <div className="mt-5 border border-hex-gold-dim bg-hex-bg p-4">
      <p role="status" className="text-sm text-hex-white">
        {children}
      </p>
      <label
        htmlFor={id}
        className="mt-3 block text-sm font-bold text-hex-white"
      >
        {label}
      </label>
      <input
        id={id}
        type="text"
        readOnly
        value={url}
        onFocus={(event) => event.target.select()}
        className="mt-2 w-full min-w-0 border-2 border-hex-border bg-hex-bg-alt px-3 py-2 text-sm text-hex-white focus:border-hex-gold focus:outline-none"
      />
      <p className="mt-2 text-xs text-hex-bronze">
        Save this link now. It cannot be retrieved after leaving this page.
      </p>
      <button
        type="button"
        onClick={() => void copy()}
        className={`${buttonClass} mt-3`}
      >
        {copyLabel}
      </button>
      {copyMessage && (
        <p role="status" className="mt-3 text-sm text-hex-bronze">
          {copyMessage}
        </p>
      )}
    </div>
  );
}
