import React, { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

/** Renders a Plotly figure; re-plots on data/layout change (used by all dashboard graphs). */
export default function Plot({ data, layout = {}, height = 320 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) Plotly.react(ref.current, data, { margin: { t: 30, b: 40 }, ...layout }, { responsive: true });
  }, [data, layout]);
  return <div ref={ref} style={{ height }} data-testid="plot" />;
}
