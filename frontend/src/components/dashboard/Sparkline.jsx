export default function Sparkline({ data = [], color = "#2dd4bf" }) {
  const values = data.map((item) => Number(item.completed ?? item.total ?? item.avg_ms ?? 0));
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${40 - (value / max) * 34 + 3}`).join(" ");

  return (
    <svg viewBox="0 0 100 44" className="h-24 w-full overflow-visible">
      <polyline fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" points={points} />
      {values.map((value, index) => (
        <circle key={`${value}-${index}`} cx={(index / Math.max(values.length - 1, 1)) * 100} cy={40 - (value / max) * 34 + 3} r="2" fill={color} />
      ))}
    </svg>
  );
}
