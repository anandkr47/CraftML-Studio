/**
 * Minimal Chart.js line chart that updates in place as new points arrive.
 */

import React, { useEffect, useRef } from 'react';
import { Chart, ChartConfiguration } from 'chart.js/auto';

interface LineChartProps {
  labels: (string | number)[];
  data: (number | null)[];
  label: string;
  color?: string;
  height?: number;
  yTitle?: string;
}

export const LineChart: React.FC<LineChartProps> = ({
  labels,
  data,
  label,
  color = '#6366f1',
  height = 220,
  yTitle,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels,
        datasets: [{ label, data, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, tension: 0.25, spanGaps: true }],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: 'step' }, ticks: { maxTicksLimit: 8 } },
          y: { title: { display: !!yTitle, text: yTitle }, beginAtZero: false },
        },
      },
    };
    chartRef.current = new Chart(canvasRef.current!, config);
    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
    // The chart is created once; data updates below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.update('none');
  }, [labels, data]);

  return (
    <div style={{ height }}>
      <canvas ref={canvasRef} />
    </div>
  );
};

export default LineChart;
