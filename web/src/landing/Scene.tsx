import { Line } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef, type MutableRefObject } from 'react'
import * as THREE from 'three'

type P = MutableRefObject<number>
const clamp = (x: number) => Math.min(1, Math.max(0, x))
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a))
const smooth = (t: number) => t * t * (3 - 2 * t)

// Camera waypoints, one per scene (progress 0..1 split into 5 equal spans).
const WAY: [number[], number[]][] = [
  [[0, 0, 6], [0, 0, 0]],
  [[0, 0, 2.6], [0, 0, 0]],
  [[2.4, 0.8, 5.5], [0.6, 0, 0]],
  [[0, 0.4, 7], [0, 0, 0]],
  [[0, 1.2, 9], [0, 0, 0]],
  [[0, 0.2, 7.5], [0, 0, 0]],
]
const v = (a: number[]) => new THREE.Vector3(...a)

function Rig({ p, still }: { p: P; still: boolean }) {
  const look = useRef(new THREE.Vector3())
  useFrame(({ camera, pointer }, dt) => {
    const s = p.current * (WAY.length - 1)
    const i = Math.min(WAY.length - 2, Math.floor(s))
    const t = smooth(s - i)
    const pos = v(WAY[i][0]).lerp(v(WAY[i + 1][0]), t)
    if (!still) { pos.x += pointer.x * 0.25; pos.y += pointer.y * 0.15 }
    camera.position.lerp(pos, 1 - Math.pow(0.001, dt)) // damped: stable under rapid scroll
    look.current.lerp(v(WAY[i][1]).lerp(v(WAY[i + 1][1]), t), 1 - Math.pow(0.001, dt))
    camera.lookAt(look.current)
  })
  return null
}

function Fingerprint({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  const beam = useRef<THREE.Mesh>(null!)
  const rings = useMemo(() => Array.from({ length: 16 }, (_, i) => {
    const pts: THREE.Vector3[] = []
    for (let k = 0; k <= 96; k++) {
      const a = (k / 96) * Math.PI * 2
      const r = 0.18 + i * 0.075 + 0.03 * Math.sin(3 * a + i * 0.7)
      pts.push(new THREE.Vector3(Math.cos(a) * r * 0.82, Math.sin(a) * r * 1.1 + Math.sin(i) * 0.04, 0))
    }
    return pts
  }), [])
  useFrame((_, dt) => {
    const show = 1 - smooth(seg(p.current, 0.38, 0.5))
    g.current.visible = show > 0.01
    g.current.scale.setScalar(0.4 + show * 0.6)
    g.current.rotation.y += dt * 0.15 * (1 - seg(p.current, 0.1, 0.3))
    const b = seg(p.current, 0.2, 0.4) // scan beam sweeps with scroll
    beam.current.position.y = -1.3 + b * 2.6
    beam.current.visible = b > 0 && b < 1
  })
  return (
    <group ref={g}>
      {rings.map((pts, i) => <Line key={i} points={pts} color="#5eead4" lineWidth={1} transparent opacity={0.35 + (i % 3) * 0.2} />)}
      <mesh ref={beam}><planeGeometry args={[2.2, 0.03]} /><meshBasicMaterial color="#67e8f9" transparent opacity={0.9} /></mesh>
    </group>
  )
}

function Terminal({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  useFrame(() => {
    const t = smooth(seg(p.current, 0.4, 0.55)) * (1 - smooth(seg(p.current, 0.62, 0.7)))
    g.current.visible = t > 0.01
    g.current.scale.setScalar(t)
    g.current.rotation.y = -0.5 + p.current * 1.2
  })
  return (
    <group ref={g} position={[0.6, -0.2, 0]}>
      <mesh><boxGeometry args={[1.1, 1.7, 0.25]} /><meshStandardMaterial color="#141f33" metalness={0.8} roughness={0.3} /></mesh>
      <mesh position={[0, 0.45, 0.13]}><planeGeometry args={[0.9, 0.6]} /><meshBasicMaterial color="#0e7490" /></mesh>
      <mesh position={[0, -0.4, 0.13]}><circleGeometry args={[0.28, 48]} /><meshBasicMaterial color="#5eead4" /></mesh>
    </group>
  )
}

function Wallet({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  const coin = useRef<THREE.Mesh>(null!)
  useFrame(() => {
    const t = smooth(seg(p.current, 0.6, 0.68)) * (1 - smooth(seg(p.current, 0.82, 0.9)))
    g.current.visible = t > 0.01
    g.current.scale.setScalar(t)
    coin.current.position.x = -2 + 4 * smooth(seg(p.current, 0.68, 0.8))
  })
  return (
    <group ref={g}>
      <mesh position={[-2, 0, 0]}><boxGeometry args={[1.2, 0.8, 0.3]} /><meshStandardMaterial color="#1e3a5f" metalness={0.6} roughness={0.4} /></mesh>
      <mesh position={[2, 0, 0]}><boxGeometry args={[1.2, 0.8, 0.3]} /><meshStandardMaterial color="#3b2f6b" metalness={0.6} roughness={0.4} /></mesh>
      <mesh ref={coin} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.28, 0.28, 0.06, 40]} /><meshStandardMaterial color="#67e8f9" emissive="#0891b2" emissiveIntensity={0.8} /></mesh>
    </group>
  )
}

const ECO = [['#2dd4bf', -2.4], ['#818cf8', -0.8], ['#67e8f9', 0.8], ['#a78bfa', 2.4]] as const
function Ecosystem({ p }: { p: P }) {
  const g = useRef<THREE.Group>(null!)
  useFrame(({ clock }) => {
    const t = smooth(seg(p.current, 0.82, 0.92))
    g.current.visible = t > 0.01
    g.current.scale.setScalar(t)
    g.current.rotation.y = Math.sin(clock.elapsedTime * 0.3) * 0.15
  })
  return (
    <group ref={g}>
      {ECO.map(([c, x], i) => (
        <mesh key={i} position={[x, Math.sin(i) * 0.2, 0]}><boxGeometry args={[1.2, 1.6, 0.2]} /><meshStandardMaterial color={c} metalness={0.5} roughness={0.35} transparent opacity={0.85} /></mesh>
      ))}
    </group>
  )
}

export default function Scene({ progress, still }: { progress: P; still: boolean }) {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ fov: 45, position: [0, 0, 6] }} frameloop={still ? 'demand' : 'always'}
      gl={{ powerPreference: 'high-performance' }} aria-hidden>
      <ambientLight intensity={0.6} />
      <pointLight position={[4, 4, 5]} intensity={60} color="#67e8f9" />
      <pointLight position={[-4, -2, 3]} intensity={30} color="#a78bfa" />
      <Rig p={progress} still={still} />
      <Fingerprint p={progress} />
      <Terminal p={progress} />
      <Wallet p={progress} />
      <Ecosystem p={progress} />
    </Canvas>
  )
}
