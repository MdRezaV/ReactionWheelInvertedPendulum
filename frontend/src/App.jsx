import { useCallback, useEffect, useRef, useState } from 'react'
import { useSimulationApi } from './hooks/useSimulationApi'
import { useSimulationSocket } from './hooks/useSimulationSocket'
import { usePerformanceMetrics } from './hooks/usePerformanceMetrics'
import ControlPanel from './components/ControlPanel'
import SimulationChart from './components/SimulationChart'
import EnergyChart from './components/EnergyChart'
import TorqueChart from './components/TorqueChart'
import PhasePlot from './components/PhasePlot'
import PendulumCanvas from './components/PendulumCanvas'
import NumericReadout from './components/NumericReadout'
import StatusBar from './components/StatusBar'
import ErrorLog from './components/ErrorLog'

function App() {
  const api = useSimulationApi()
  const { connected, latest, status: wsStatus, params: wsParams, send, getBuffer, clearBuffer, getMetricsRef } = useSimulationSocket()
  const socketMetricsRef = getMetricsRef()
  const { fps, bytesPerSec, msgsPerSec, errors, addError, clearErrors } = usePerformanceMetrics(socketMetricsRef)
  const [status, setStatus] = useState(null)
  const [params, setParams] = useState(null)

  useEffect(() => {
    if (wsParams) setParams(wsParams)
  }, [wsParams])

  useEffect(() => {
    if (wsStatus) setStatus(wsStatus)
  }, [wsStatus])

  const handleStart = useCallback(async () => { await api.start() }, [api])
  const handleStop = useCallback(async () => { await api.stop() }, [api])

  const handleReset = useCallback(async () => { await api.reset(); clearBuffer() }, [api, clearBuffer])
  const handleStep = useCallback(async (steps) => { await api.step(steps) }, [api])
  const handleSetMode = useCallback(async (mode) => { await api.setControlMode(mode) }, [api])
  const handleSetManualVoltage = useCallback(async (voltage) => { await api.setManualVoltage(voltage) }, [api])

  const handleUpdateParams = useCallback(async (body) => {
    try { await api.updateParams(body) }
    catch (err) { addError(`بروزرسانی پارامتر ناموفق: ${err.message}`) }
  }, [api, addError])

  const handleDisturbance = useCallback(async (voltage, durationSteps) => {
    try { await api.applyDisturbance(voltage, durationSteps) }
    catch (err) { addError(`اغتشاش ناموفق: ${err.message}`) }
  }, [api, addError])

  const handleSetSpeed = useCallback(async (multiplier) => {
    try { await api.setSpeed(multiplier) }
    catch (err) { addError(`تغییر سرعت ناموفق: ${err.message}`) }
  }, [api, addError])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg font-sans">
      <header className="px-6 py-3 border-b border-border flex-shrink-0 bg-surface/80 backdrop-blur-sm">
        <h1 className="text-lg font-bold text-text-h tracking-tight">
          پاندول معکوس چرخ عکس‌العملی
        </h1>
      </header>

      <StatusBar
        status={status}
        connected={connected}
        warnings={status?.warnings}
        fps={fps}
        bytesPerSec={bytesPerSec}
        msgsPerSec={msgsPerSec}
      />

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-[310px] border-l border-border overflow-y-auto flex-shrink-0 bg-surface/50">
          <ControlPanel
            status={status}
            params={params}
            onStart={handleStart}
            onStop={handleStop}
            onReset={handleReset}
            onStep={handleStep}
            onSetMode={handleSetMode}
            onSetManualVoltage={handleSetManualVoltage}
            onUpdateParams={handleUpdateParams}
            onDisturbance={handleDisturbance}
            onSetSpeed={handleSetSpeed}
          />
        </aside>

        <section className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          <div className="flex gap-4 flex-wrap">
            <PendulumCanvas latest={latest} params={params} />
            <PhasePlot getBuffer={getBuffer} />
            <NumericReadout latest={latest} />
          </div>
          <SimulationChart getBuffer={getBuffer} />
          <div className="flex gap-4 flex-wrap">
            <EnergyChart getBuffer={getBuffer} />
            <TorqueChart getBuffer={getBuffer} />
          </div>
        </section>
      </main>

      <ErrorLog errors={errors} onClear={clearErrors} />
    </div>
  )
}

export default App