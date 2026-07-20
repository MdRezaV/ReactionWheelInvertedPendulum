import { useCallback, useEffect, useState } from 'react'
import { useSimulationApi } from './hooks/useSimulationApi'
import { useSimulationSocket } from './hooks/useSimulationSocket'
import ControlPanel from './components/ControlPanel'
import SimulationChart from './components/SimulationChart'
import EnergyChart from './components/EnergyChart'
import TorqueChart from './components/TorqueChart'
import PhasePlot from './components/PhasePlot'
import PendulumCanvas from './components/PendulumCanvas'
import NumericReadout from './components/NumericReadout'
import StatusBar from './components/StatusBar'
import './App.css'

function App() {
  const api = useSimulationApi()
  const { connected, latest, status: wsStatus, params: wsParams, send, getBuffer, clearBuffer } = useSimulationSocket()
  const [status, setStatus] = useState(null)
  const [params, setParams] = useState(null)

  useEffect(() => {
    if (wsParams) {
      setParams(wsParams)
    }
  }, [wsParams])

  useEffect(() => {
    if (wsStatus) {
      setStatus(wsStatus)
    }
  }, [wsStatus])

  const handleStart = useCallback(async () => {
    await api.start()
  }, [api])

  const handleStop = useCallback(async () => {
    await api.stop()
  }, [api])

  const handlePause = useCallback(async () => {
    await api.pause()
  }, [api])

  const handleResume = useCallback(async () => {
    await api.resume()
  }, [api])

  const handleReset = useCallback(async () => {
    await api.reset()
    clearBuffer()
  }, [api, clearBuffer])

  const handleStep = useCallback(async (steps) => {
    await api.step(steps)
  }, [api])

  const handleSetMode = useCallback(async (mode) => {
    await api.setControlMode(mode)
  }, [api])

  const handleSetManualVoltage = useCallback(async (voltage) => {
    await api.setManualVoltage(voltage)
  }, [api])

  const handleUpdateParams = useCallback(async (body) => {
    try {
      await api.updateParams(body)
    } catch {
      // Ignore validation errors silently
    }
  }, [api])

  const handleDisturbance = useCallback(async (voltage, durationSteps) => {
    try {
      await api.applyDisturbance(voltage, durationSteps)
    } catch {
      // Ignore
    }
  }, [api])

  const handleSetSpeed = useCallback(async (multiplier) => {
    try {
      await api.setSpeed(multiplier)
    } catch {
      // Ignore
    }
  }, [api])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Reaction Wheel Inverted Pendulum</h1>
      </header>

      <StatusBar status={status} connected={connected} warnings={status?.warnings} />

      <main className="app-main">
        <aside className="app-sidebar">
          <ControlPanel
            status={status}
            params={params}
            onStart={handleStart}
            onStop={handleStop}
            onPause={handlePause}
            onResume={handleResume}
            onReset={handleReset}
            onStep={handleStep}
            onSetMode={handleSetMode}
            onSetManualVoltage={handleSetManualVoltage}
            onUpdateParams={handleUpdateParams}
            onDisturbance={handleDisturbance}
            onSetSpeed={handleSetSpeed}
          />
        </aside>

        <section className="app-content">
          <div className="viz-row">
            <PendulumCanvas latest={latest} />
            <PhasePlot getBuffer={getBuffer} />
            <NumericReadout latest={latest} />
          </div>
          <SimulationChart getBuffer={getBuffer} />
          <div className="viz-row">
            <EnergyChart getBuffer={getBuffer} />
            <TorqueChart getBuffer={getBuffer} />
          </div>
        </section>
      </main>
    </div>
  )
}

export default App