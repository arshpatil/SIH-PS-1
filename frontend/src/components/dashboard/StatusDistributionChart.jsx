import React from 'react'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { Card, CardHeader } from '../ui/Card'
import { useApp } from '../../context/AppContext'

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0]
    return (
      <div className="bg-slate-900 text-white px-3 py-2 rounded-lg text-xs shadow-lg border border-slate-700">
        <p className="font-semibold">{data.name}</p>
        <p className="text-slate-300 mt-0.5">
          Count: <span className="text-white font-bold">{data.value}</span> record(s)
        </p>
      </div>
    )
  }
  return null
}

export function StatusDistributionChart() {
  const { statusDistribution, stats } = useApp()

  return (
    <Card className="flex flex-col h-full">
      <CardHeader
        title="FDR Status Distribution"
        subtitle={`Current breakdown across all ${stats.totalFdrs} registered records`}
      />

      <div className="flex-1 flex flex-col justify-between">
        {/* Donut Chart */}
        <div className="h-48 w-full relative">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={statusDistribution}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={75}
                paddingAngle={3}
                dataKey="value"
              >
                {statusDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} stroke="#FFFFFF" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>

          {/* Centered Total Label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-bold text-slate-800 leading-none">{stats.totalFdrs}</span>
            <span className="text-[10px] uppercase font-semibold text-slate-600 mt-0.5 tracking-wider">
              Total FDRs
            </span>
          </div>
        </div>

        {/* Legend List */}
        <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-slate-100">
          {statusDistribution.map((item, index) => (
            <div key={index} className="flex items-center justify-between text-xs p-1.5 rounded-lg hover:bg-slate-50">
              <div className="flex items-center gap-2 truncate">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-slate-600 truncate font-medium">{item.name}</span>
              </div>
              <span className="font-bold text-slate-800 ml-2">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
