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
  const { connected, latest, send, getBuffer, clearBuffer } = useSimulationSocket()

  const [status, setStatus] = useState(null)
  const [params, setParams] = useState(null)

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.getStatus()
      setStatus(s)
    } catch {
      // Backend may not be running
    }
  }, [api])

  const refreshParams = useCallback(async () => {
    try {
      const p = await api.getParams()
      setParams(p)
    } catch {
      // Ignore
    }
  }, [api])

  useEffect(() => {
    refreshStatus()
    refreshParams()
    const interval = setInterval(refreshStatus, 2000)
    return () => clearInterval(interval)
  }, [refreshStatus, refreshParams])

  const handleStart = useCallback(async () => {
    await api.start()
    refreshStatus()
  }, [api, refreshStatus])

  const handleStop = useCallback(async () => {
    await api.stop()
    refreshStatus()
  }, [api, refreshStatus])

  const handlePause = useCallback(async () => {
    await api.pause()
    refreshStatus()
  }, [api, refreshStatus])

  const handleResume = useCallback(async () => {
    await api.resume()
    refreshStatus()
  }, [api, refreshStatus])

  const handleReset = useCallback(async () => {
    await api.reset()
    clearBuffer()
    refreshStatus()
  }, [api, clearBuffer, refreshStatus])

  const handleStep = useCallback(async (steps) => {
    await api.step(steps)
    refreshStatus()
  }, [api, refreshStatus])

  const handleSetMode = useCallback(async (mode) => {
    await api.setControlMode(mode)
    refreshStatus()
  }, [api, refreshStatus])

  const handleSetManualVoltage = useCallback(async (voltage) => {
    await api.setManualVoltage(voltage)
  }, [api])

  const handleUpdateParams = useCallback(async (body) => {
    try {
      const p = await api.updateParams(body)
      setParams(p)
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
      refreshStatus()
    } catch {
      // Ignore
    }
  }, [api, refreshStatus])

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