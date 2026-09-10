import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface DataPoint {
  sequence: number;
  count: number;
  amount: number;
}

export function SalesBySequenceChart({ data }: { data: DataPoint[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="sequence" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="amount" fill="#10b981" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
