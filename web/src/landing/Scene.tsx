import { ContactShadows, Edges } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useMemo, useRef, type MutableRefObject, type ReactNode } from 'react'
import * as THREE from 'three'

// "Technical drawing" look: paper-coloured solids outlined in ink, one cobalt accent and a
// highlighter-yellow coin. Every motion is a function of scroll progress, so it is reversible.

type P = MutableRefObject<number>
const clamp = (x: number) => Math.min(1, Math.max(0, x))
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a))
const smooth = (t: number) => t * t * (3 - 2 * t)
const window_ = (p: number, a: number, b: number, c: number, d: number) => smooth(seg(p, a, b)) * (1 - smooth(seg(p, c, d)))

const INK = '#16140f'
const PAPER = '#fbf9f4'
const CARD = '#efe8da'
const COBALT = '#2236c8'
const HI = '#e6ff3a'

// Camera waypoints, one per section.
const WAY: [number[], number[]][] = [
  [[0.3, 0.6, 6.2], [0, 0, 0]],
  [[-1.2, 1.8, 4.2], [0, 0, 0]],
  [[3.2, 3.4, 6.2], [0, 0.3, 0]],
  [[0, 1.2, 7.4], [0, 0, 0]],
  [[-2.6, 2.4, 7.6], [0, 0.2, 0]],
  [[0, 0.8, 7.2], [0, 0, 0]],
]
const v = (a: number[]) => new THREE.Vector3(...a)

function Rig({ p, still }: { p: P; still: boolean }) {
  const look = useRef(new THREE.Vector3())
  const aspect = useThree((s) => s.size.width / s.size.height)
  const back = aspect < 1 ? 1 + (1 - aspect) * 0.9 : 1
  useFrame(({ camera, pointer }, dt) => {
    const s = p.current * (WAY.length - 1)
    const i = Math.min(WAY.length - 2, Math.floor(s))
    const t = smooth(s - i)
    const pos = v(WAY[i][0]).lerp(v(WAY[i + 1][0]), t)
    pos.multiplyScalar(back)
    if (!still) { pos.x += pointer.x * 0.35; pos.y += pointer.y * 0.2 }
    const k = 1 - Math.pow(0.002, dt)
    camera.position.lerp(pos, k)
    look.current.lerp(v(WAY[i][1]).lerp(v(WAY[i + 1][1]), t), k)
    camera.lookAt(look.current)
  })
  return null
}

/** A solid with an ink outline. */
function Inked({ geo, color = PAPER, pos, rot, children }: {
  geo: ReactNode; color?: string; pos?: [number, number, number]; rot?: [number, number, number]; children?: ReactNode
}) {
  return (
    <mesh position={pos} rotation={rot}>
      {geo}
      <meshStandardMaterial color={color} roughness={0.95} metalness={0} />
      <Edges color={INK} threshold={20} />
      {children}
    </mesh>
  )
}

// ---------- 01: the sensor module and its fingerprint ----------
function ridges() {
  // Open whorl loops with a small core arch, the way a real print reads.
  const out: THREE.TubeGeometry[] = []
  for (let i = 0; i < 17; i++) {
    const pts: THREE.Vector3[] = []
    const gap = 0.35 + (i % 4) * 0.12 // every loop leaves a small break: looks drawn, not generated
    const start = -Math.PI / 2 + gap / 2 + i * 0.21
    for (let k = 0; k <= 80; k++) {
      const a = start + (k / 80) * (Math.PI * 2 - gap)
      const r = 0.08 + i * 0.058 + 0.018 * Math.sin(3 * a + i)
      pts.push(new THREE.Vector3(Math.cos(a) * r * 0.84, 0, Math.sin(a) * r * 1.12))
    }
    out.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 140, 0.011, 5, false))
  }
  return out
}

function Sensor({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  const scan = useRef<THREE.Mesh>(null!)
  const print = useRef<THREE.Group>(null!)
  const geos = useMemo(ridges, [])
  useFrame(({ clock, pointer }) => {
    const t = 1 - smooth(seg(p.current, 0.24, 0.3))
    g.current.visible = t > 0.01
    g.current.scale.setScalar(0.3 + 0.7 * t)
    g.current.rotation.set(0.95 - p.current * 1.4, -0.4 + p.current * 2.2, 0)
    // ridges ripple toward the pointer, like a finger pressing the glass
    print.current.children.forEach((c, i) => {
      c.position.y = 0.02 * Math.sin(clock.elapsedTime * 1.6 - i * 0.5) * (1 + pointer.x) + 0.004 * i
    })
    const s = seg(p.current, 0.04, 0.22)
    scan.current.position.z = -1.0 + s * 2.0
    scan.current.visible = s > 0 && s < 1
  })
  return (
    <group ref={g}>
      {/* R307S-style module: housing, glass window, six-pin connector */}
      <Inked geo={<boxGeometry args={[2.3, 0.32, 2.7]} />} color={CARD} pos={[0, -0.18, 0]} />
      <Inked geo={<boxGeometry args={[1.8, 0.04, 2.2]} />} color={PAPER} pos={[0, 0.0, 0]} />
      {Array.from({ length: 6 }, (_, i) => (
        <Inked key={i} geo={<boxGeometry args={[0.1, 0.1, 0.22]} />} color={INK} pos={[-0.38 + i * 0.15, -0.18, 1.45]} />
      ))}
      <group ref={print} position={[0, 0.03, 0]}>
        {geos.map((geo, i) => (
          <mesh key={i} geometry={geo}><meshBasicMaterial color={i % 5 === 3 ? COBALT : INK} /></mesh>
        ))}
      </group>
      <mesh ref={scan} position={[0, 0.08, 0]}>
        <boxGeometry args={[1.86, 0.02, 0.05]} />
        <meshBasicMaterial color={COBALT} />
      </mesh>
    </group>
  )
}

// ---------- 02: the terminal, exploded ----------
const KEYS = '123A456B789C*0#D'
function Terminal({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  const layers = useRef<THREE.Group[]>([])
  const keys = useRef<THREE.Group>(null!)
  const led = useRef<THREE.MeshBasicMaterial>(null!)
  useFrame(({ clock }) => {
    const t = window_(p.current, 0.27, 0.32, 0.5, 0.54)
    g.current.visible = t > 0.01
    g.current.scale.setScalar(0.85 * t)
    g.current.rotation.y = -0.6 + p.current * 1.6
    const ex = smooth(seg(p.current, 0.32, 0.42)) // explode
    layers.current.forEach((l, i) => { if (l) l.position.y = i * 0.12 + ex * i * 0.62 })
    // type "4 0 #" on a loop
    const beat = Math.floor(clock.elapsedTime * 2.2) % 6
    const pressed = ['4', '0', '#', '', '', ''][beat]
    keys.current.children.forEach((k, i) => { k.position.y = KEYS[i] === pressed ? -0.035 : 0 })
    led.current.color.set(beat >= 3 ? COBALT : '#c9c3b6')
  })
  const L = (i: number) => (el: THREE.Group | null) => { if (el) layers.current[i] = el }
  return (
    <group ref={g} position={[0, -0.4, 0]}>
      <group ref={L(0)}>
        <Inked geo={<boxGeometry args={[2.2, 0.2, 3.0]} />} color={CARD} />
      </group>
      <group ref={L(1)}>
        {/* ESP32 NodeMCU-32S: dark board, metal can, two pin headers */}
        <Inked geo={<boxGeometry args={[0.95, 0.05, 2.0]} />} color="#2b2a25" />
        <Inked geo={<boxGeometry args={[0.6, 0.1, 0.75]} />} color="#d9d4c8" pos={[0, 0.08, -0.45]} />
        {Array.from({ length: 19 }, (_, i) => [-0.42, 0.42].map((x) => (
          <mesh key={`${i}${x}`} position={[x, 0.06, -0.9 + i * 0.1]}><boxGeometry args={[0.05, 0.08, 0.05]} /><meshBasicMaterial color={HI} /></mesh>
        )))}
      </group>
      <group ref={L(2)}>
        {/* keypad plate and 16 keys */}
        <Inked geo={<boxGeometry args={[1.5, 0.06, 1.5]} />} color={PAPER} pos={[0, 0, 0.55]} />
        <group ref={keys} position={[0, 0.08, 0.55]}>
          {KEYS.split('').map((k, i) => (
            <group key={k} position={[-0.51 + (i % 4) * 0.34, 0, -0.51 + Math.floor(i / 4) * 0.34]}>
              <Inked geo={<boxGeometry args={[0.26, 0.08, 0.26]} />} color={/[A-D]/.test(k) ? HI : PAPER} />
            </group>
          ))}
        </group>
        {/* fingerprint window and status LED */}
        <Inked geo={<cylinderGeometry args={[0.32, 0.32, 0.06, 40]} />} color="#2b2a25" pos={[0, 0, -0.85]} />
        <mesh position={[0.75, 0.06, -1.25]}><sphereGeometry args={[0.07, 20, 20]} /><meshBasicMaterial ref={led} color={COBALT} /></mesh>
      </group>
      <group ref={L(3)}>
        {/* lid frame, open in the middle */}
        <Inked geo={<boxGeometry args={[2.2, 0.06, 0.18]} />} color={CARD} pos={[0, 0, -1.41]} />
        <Inked geo={<boxGeometry args={[2.2, 0.06, 0.18]} />} color={CARD} pos={[0, 0, 1.41]} />
        <Inked geo={<boxGeometry args={[0.18, 0.06, 3.0]} />} color={CARD} pos={[-1.01, 0, 0]} />
        <Inked geo={<boxGeometry args={[0.18, 0.06, 3.0]} />} color={CARD} pos={[1.01, 0, 0]} />
      </group>
    </group>
  )
}

// ---------- 03: the ledger ----------
function Ledger({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  const coin = useRef<THREE.Group>(null!)
  const sheets = useRef<THREE.Group>(null!)
  useFrame(() => {
    const t = window_(p.current, 0.52, 0.56, 0.7, 0.74)
    g.current.visible = t > 0.01
    g.current.scale.setScalar(t)
    const m = smooth(seg(p.current, 0.55, 0.66))
    coin.current.position.set(-1.3 + 2.6 * m, 0.55 + Math.sin(m * Math.PI) * 1.1, 0)
    coin.current.rotation.y = m * Math.PI * 3
    const n = Math.round(seg(p.current, 0.55, 0.68) * 9)
    sheets.current.children.forEach((c, i) => { c.visible = i < n })
  })
  return (
    <group ref={g}>
      <Inked geo={<boxGeometry args={[1.1, 0.45, 0.9]} />} color={PAPER} pos={[-1.3, 0, 0]} />
      <Inked geo={<boxGeometry args={[1.1, 0.45, 0.9]} />} color={COBALT} pos={[1.3, 0, 0]} />
      <group ref={coin}>
        <Inked geo={<cylinderGeometry args={[0.32, 0.32, 0.07, 44]} />} color={HI} rot={[Math.PI / 2, 0, 0]} />
      </group>
      {/* each payment adds a pair of ledger rows: a sheet on the stack */}
      <group ref={sheets} position={[0, -0.22, 1.25]}>
        {Array.from({ length: 9 }, (_, i) => (
          <group key={i} position={[0, i * 0.045, 0]} rotation={[0, (i % 3 - 1) * 0.06, 0]}>
            <Inked geo={<boxGeometry args={[1.3, 0.025, 0.9]} />} color={i % 2 ? PAPER : CARD} />
          </group>
        ))}
      </group>
    </group>
  )
}

// ---------- 04: dashboards and the live screen ----------
function Screens({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  useFrame(({ clock }) => {
    const t = smooth(seg(p.current, 0.72, 0.78))
    g.current.visible = t > 0.01
    g.current.scale.setScalar(t)
    g.current.rotation.y = Math.sin(clock.elapsedTime * 0.25) * 0.2 + (p.current - 0.8) * 1.2
  })
  const panel = (x: number, ry: number, c: string, rows: number) => (
    <group position={[x, 0.2, Math.abs(x) * -0.35]} rotation={[0, ry, 0]}>
      <Inked geo={<boxGeometry args={[1.25, 1.7, 0.06]} />} color={c} />
      {Array.from({ length: rows }, (_, i) => (
        <mesh key={i} position={[-0.12 + (i % 2) * 0.05, 0.55 - i * 0.2, 0.04]}>
          <boxGeometry args={[0.8 - (i % 3) * 0.18, 0.04, 0.01]} /><meshBasicMaterial color={INK} />
        </mesh>
      ))}
    </group>
  )
  return (
    <group ref={g}>
      {panel(-1.6, 0.45, PAPER, 6)}
      {panel(1.6, -0.45, PAPER, 5)}
      <group position={[0, 0.1, 0.4]}>
        <Inked geo={<boxGeometry args={[1.5, 2.1, 0.22]} />} color={CARD} />
        <mesh position={[0, 0.45, 0.12]}><boxGeometry args={[1.15, 0.7, 0.01]} /><meshBasicMaterial color="#c8d2ae" /></mesh>
        <mesh position={[0, 0.45, 0.13]}><boxGeometry args={[0.6, 0.1, 0.01]} /><meshBasicMaterial color="#1f2a12" /></mesh>
        {Array.from({ length: 12 }, (_, i) => (
          <mesh key={i} position={[-0.42 + (i % 4) * 0.28, -0.25 - Math.floor(i / 4) * 0.22, 0.13]}>
            <boxGeometry args={[0.2, 0.14, 0.04]} /><meshBasicMaterial color={i === 3 ? HI : INK} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

function Stage({ children }: { children: ReactNode }) {
  const aspect = useThree((s) => s.size.width / s.size.height)
  const portrait = aspect < 1
  return (
    <group position={[aspect > 1.2 ? 1.7 : 0, portrait ? 2.3 : 0, 0]} scale={portrait ? Math.max(0.55, aspect) : 1}>
      {children}
    </group>
  )
}

export default function Scene({ progress, still }: { progress: P; still: boolean }) {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ fov: 40, position: [0, 0.6, 6.2] }} frameloop={still ? 'demand' : 'always'}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }} aria-hidden>
      <ambientLight intensity={1.6} />
      <directionalLight position={[3, 6, 4]} intensity={1.4} />
      <Rig p={progress} still={still} />
      <Stage>
        <Sensor p={progress} />
        <Terminal p={progress} />
        <Ledger p={progress} />
        <Screens p={progress} />
        <ContactShadows position={[0, -1.25, 0]} opacity={0.28} scale={9} blur={2.6} far={3} color={INK} />
      </Stage>
    </Canvas>
  )
}
