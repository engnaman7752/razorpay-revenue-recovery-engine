export function inr(paise) {
  if (paise == null) return "–";
  return "₹" + (paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

/** Compact form for axis ticks and dense labels: ₹15.4L, ₹4.6L, ₹82k */
export function inrCompact(paise) {
  if (paise == null) return "–";
  const r = paise / 100;
  if (r >= 1e7) return "₹" + (r / 1e7).toFixed(2) + "Cr";
  if (r >= 1e5) return "₹" + (r / 1e5).toFixed(1) + "L";
  if (r >= 1e3) return "₹" + Math.round(r / 1e3) + "k";
  return "₹" + Math.round(r);
}

export function shortId(id) {
  return id ? id.slice(0, 8) : "";
}

export function ts(t) {
  if (!t) return "";
  return new Date(t).toLocaleString("en-IN", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

/** status -> {label, tone} where tone maps to a chip style in components/Chip */
export const STATUS_TONE = {
  DETECTED: "idle",
  IN_PROGRESS: "info",
  WAITING_APPROVAL: "warning",
  SCHEDULED: "info",
  RECOVERED: "good",
  ESCALATED: "warning",
  CLOSED: "idle",
};

export const CAUSE_LABEL = {
  SOFT_DECLINE: "Soft decline",
  TRANSIENT: "Transient",
  HARD_DECLINE: "Hard decline",
  CUSTOMER_ACTION: "Customer action",
  UNRECOVERABLE: "Unrecoverable",
};
