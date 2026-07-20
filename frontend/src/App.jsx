import { memo, useCallback } from 'react'
import { useSimulationApi } from './hooks/useSimulationApi'
import { useSimulationSocket } from './hooks/useSimulationSocket'
import { usePerformanceMetrics } from './hooks/usePerformanceMetrics'
import ControlPanel from './components/ControlPanel'
import SimulationChart from './components/SimulationChart'
import EnergyChart from './components/EnergyChart'
import TorqueChart from './components/TorqueChart'
import PendulumCanvas from './components/PendulumCanvas'
import NumericReadout from './components/NumericReadout'
import StatusBar from './components/StatusBar'
import ErrorLog from './components/ErrorLog'

const MemoControlPanel = memo(ControlPanel)
const MemoEnergyChart = memo(EnergyChart)
const MemoTorqueChart = memo(TorqueChart)
const MemoSimulationChart = memo(SimulationChart)

function App() {
  const api = useSimulationApi()
  const { connected, latest, status, params, send, getBuffer, clearBuffer, getMetricsRef } = useSimulationSocket()
  const socketMetricsRef = getMetricsRef()
  const { fps, bytesPerSec, msgsPerSec, errors, addError, clearErrors } = usePerformanceMetrics(socketMetricsRef)

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
      <StatusBar
        status={status}
        connected={connected}
        warnings={status?.warnings}
        fps={fps}
        bytesPerSec={bytesPerSec}
        msgsPerSec={msgsPerSec}
      />

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-[272px] border-l border-border overflow-y-auto flex-shrink-0 bg-surface/40">
          <MemoControlPanel
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

        <div className="flex flex-1 overflow-hidden">
          <section className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
            <NumericReadout latest={latest} />
            <MemoEnergyChart getBuffer={getBuffer} />
            <MemoTorqueChart getBuffer={getBuffer} />
            <MemoSimulationChart getBuffer={getBuffer} />
          </section>

          <section className="flex-1 flex flex-col border-r border-border p-3 min-h-0">
            <PendulumCanvas latest={latest} params={params} />
          </section>
        </div>
      </main>

      <ErrorLog errors={errors} onClear={clearErrors} />
    </div>
  )
}

export default App