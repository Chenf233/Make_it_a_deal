import * as THREE from "/static/js/vendor/three/three.module.min.js";

const COLORS = {
    cyan: 0x72f7ff,
    blue: 0x237bc5,
    violet: 0xa979ff,
    deepViolet: 0x5732a8,
    white: 0xe8fdff,
    ground: 0x071126,
};

const MAP_CONFIG = {
    scan: {
        cycleDuration: 4,
        travelDuration: 4,
        maxRadius: 23,
    },
    roads: {
        arterialWidth: 0.16,
    },
};

const CITY_PATHS = {
    arterials: [
        [[-19, 3.5], [-13, 3.1], [-8, 2.1], [-3, 0.8], [2.5, 1.2], [8.5, 3], [18.5, 3.8]],
        [[-18, -7.2], [-12.5, -5.8], [-7.2, -4.2], [-2.2, -1.2], [4.2, -1.5], [10.8, -4], [18, -6.8]],
        [[-9, 12], [-7.1, 8.1], [-5.4, 4.2], [-3.2, 0.8], [-0.8, -4.5], [0.5, -12]],
        [[10.6, 12], [9.2, 8.2], [7.5, 4.5], [5.2, 0.8], [5.1, -4], [7, -11]],
        [[-18, -0.6], [-12, -0.9], [-7, 0.2], [-2.5, 2.5], [2, 4.2], [7, 5.7], [16, 7.2]],
    ],
};

const layouts = {
    wide: {
        core: [0, 0], station1: [-7.2, -1.5], station2: [2.1, 4.7], station3: [7.5, -1.1],
        souya: [-12.2, 3.9], misaki: [12.3, 3.8], catvillage: [13.2, -4.5], tohno: [-12.8, -4.2],
        millennium: [0.3, 8.4], shirainu: [2.1, -8.1], spirit: [-8.2, 7.5], kuonji: [8.5, 7.3],
    },
    standard: {
        core: [0, 0], station1: [-5.2, -1.1], station2: [1.7, 3.7], station3: [5.6, -0.8],
        souya: [-9.2, 3.2], misaki: [9.4, 3.1], catvillage: [9.2, -4.1], tohno: [-9.5, -3.8],
        millennium: [0.2, 7.2], shirainu: [1.4, -7], spirit: [-6.1, 6.2], kuonji: [6.5, 6.1],
    },
    compact: {
        core: [0, -0.2], station1: [-3.8, -0.8], station2: [0.2, 3.5], station3: [3.8, -0.5],
        souya: [-6.1, 2.7], misaki: [6.1, 2.8], catvillage: [5.2, -4.5], tohno: [-5.5, -4.3],
        millennium: [0, 6.5], shirainu: [0.3, -6.6], spirit: [-4.5, 5.3], kuonji: [4.6, 5.2],
    },
};

const nodeConfig = [
    { id: "core", name: "SMARTSTATION", type: "core", volume: 0 },
    { id: "station1", name: "PILOT", type: "relay", volume: 184 },
    { id: "station2", name: "PILOT", type: "relay", volume: 226 },
    { id: "station3", name: "PILOT", type: "relay", volume: 169 },
    { id: "souya", name: "总耶市", type: "destination", volume: 243, via: "station1" },
    { id: "misaki", name: "三咲市", type: "destination", volume: 198, via: "station2" },
    { id: "catvillage", name: "超级猫姬村", type: "destination", volume: 286, via: "station3" },
    { id: "tohno", name: "远野府邸", type: "destination", volume: 112, via: "station1" },
    { id: "millennium", name: "千年城", type: "destination", volume: 176, via: "station2" },
    { id: "shirainu", name: "白犬塚", type: "destination", volume: 149, via: "station3" },
    { id: "spirit", name: "灵子研究区", type: "destination", volume: 207, via: "station1" },
    { id: "kuonji", name: "久远寺工房", type: "destination", volume: 134, via: "station2" },
];

const routeConfig = nodeConfig
    .filter((node) => node.type === "destination")
    .map((node) => ["core", node.via, node.id]);

const container = document.querySelector("#scene");
const labelLayer = document.querySelector("#labels");
const detail = document.querySelector("#node-detail");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x030612);
scene.fog = new THREE.FogExp2(0x030612, 0.026);

const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 120);
const world = new THREE.Group();
scene.add(world);

const ambient = new THREE.AmbientLight(0x4266aa, 1.15);
const moonLight = new THREE.DirectionalLight(0xa8c7ff, 2.2);
moonLight.position.set(-8, 14, 10);
const coreLight = new THREE.PointLight(COLORS.cyan, 30, 22, 2);
coreLight.position.set(0, 3, 0);
scene.add(ambient, moonLight, coreLight);

const nodes = new Map();
const routes = [];
const flights = [];
const shockwaves = [];
const clock = new THREE.Clock();
const pointer = new THREE.Vector2();
const terrainMaterials = [];
let currentLayout = "standard";
let nextDispatchAt = 0;
let efficiencyValue = 36.8;
let lastScanCycle = -1;
let lowMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function material(color, opacity = 1) {
    return new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, depthWrite: opacity === 1, blending: opacity < 1 ? THREE.AdditiveBlending : THREE.NormalBlending });
}

function lineMaterial(color, opacity = 1) {
    return new THREE.LineBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending });
}

function terrainHeight(x, z) {
    const radius = Math.hypot(x * 0.82, z);
    const centerMask = THREE.MathUtils.smoothstep(radius, 2.2, 6.2);
    const broad = Math.sin(x * 0.31) * 0.28 + Math.cos(z * 0.46) * 0.24;
    const diagonal = Math.sin((x + z) * 0.22) * 0.2 + Math.cos((x - z) * 0.27) * 0.16;
    const ridge = Math.sin(x * 0.13 + Math.cos(z * 0.31) * 1.4) * 0.18;
    const basin = -0.34 * Math.exp(-((x + 7.5) ** 2 + (z - 2.5) ** 2) / 32);
    const rise = 0.4 * Math.exp(-((x - 8.5) ** 2 + (z + 4.2) ** 2) / 38);
    return (broad + diagonal + ridge + basin + rise) * centerMask;
}

function registerTerrainMaterial(material) {
    terrainMaterials.push(material);
    return material;
}

function createTerrainMaterial() {
    return registerTerrainMaterial(new THREE.ShaderMaterial({
        uniforms: {
            uTime: { value: 0 },
            uScanRadius: { value: 0 },
            uMaxRadius: { value: MAP_CONFIG.scan.maxRadius },
        },
        vertexShader: `
            uniform float uScanRadius;
            varying vec3 vWorldPosition;
            varying vec3 vNormal;
            void main() {
                vec3 displaced = position;
                float radius = length(position.xz);
                float wave = 1.0 - smoothstep(0.0, 0.95, abs(radius - uScanRadius));
                displaced.y += wave * 0.13;
                vec4 world = modelMatrix * vec4(displaced, 1.0);
                vWorldPosition = world.xyz;
                vNormal = normalize(normalMatrix * normal);
                gl_Position = projectionMatrix * viewMatrix * world;
            }
        `,
        fragmentShader: `
            uniform float uTime;
            uniform float uScanRadius;
            uniform float uMaxRadius;
            varying vec3 vWorldPosition;
            varying vec3 vNormal;
            void main() {
                float radius = length(vWorldPosition.xz);
                float wave = 1.0 - smoothstep(0.0, 0.85, abs(radius - uScanRadius));
                float wake = 1.0 - smoothstep(0.0, 4.8, abs(radius - max(0.0, uScanRadius - 2.45)));
                float edgeFade = 1.0 - smoothstep(uMaxRadius - 5.0, uMaxRadius, radius);
                vec3 lightDirection = normalize(vec3(-0.35, 0.82, 0.45));
                float light = 0.34 + max(dot(normalize(vNormal), lightDirection), 0.0) * 0.42;
                float heightGlow = smoothstep(-0.45, 0.7, vWorldPosition.y) * 0.08;
                vec3 base = vec3(0.018, 0.045, 0.105) * light;
                base += vec3(0.018, 0.055, 0.11) * heightGlow;
                base += vec3(0.16, 0.74, 0.95) * wave * 0.22;
                base += vec3(0.28, 0.12, 0.58) * wake * 0.1;
                gl_FragColor = vec4(base * edgeFade, 1.0);
            }
        `,
    }));
}

function createContourMaterial() {
    return registerTerrainMaterial(new THREE.ShaderMaterial({
        uniforms: {
            uScanRadius: { value: 0 },
            uMaxRadius: { value: MAP_CONFIG.scan.maxRadius },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        vertexShader: `
            varying vec3 vWorldPosition;
            void main() {
                vec4 world = modelMatrix * vec4(position, 1.0);
                vWorldPosition = world.xyz;
                gl_Position = projectionMatrix * viewMatrix * world;
            }
        `,
        fragmentShader: `
            uniform float uScanRadius;
            uniform float uMaxRadius;
            varying vec3 vWorldPosition;
            void main() {
                float radius = length(vWorldPosition.xz);
                float wave = 1.0 - smoothstep(0.0, 0.9, abs(radius - uScanRadius));
                float wake = 1.0 - smoothstep(0.0, 2.7, abs(radius - max(0.0, uScanRadius - 1.5)));
                float edgeFade = 1.0 - smoothstep(uMaxRadius - 4.0, uMaxRadius, radius);
                float alpha = (0.075 + wave * 0.78 + wake * 0.16) * edgeFade;
                vec3 color = mix(vec3(0.29, 0.24, 0.65), vec3(0.42, 0.94, 1.0), wave);
                gl_FragColor = vec4(color, alpha);
            }
        `,
    }));
}

function buildTerrainGeometry(width, depth, columns, rows) {
    const geometry = new THREE.PlaneGeometry(width, depth, columns, rows);
    geometry.rotateX(-Math.PI / 2);
    const positions = geometry.attributes.position;
    for (let i = 0; i < positions.count; i += 1) {
        const x = positions.getX(i);
        const z = positions.getZ(i);
        positions.setY(i, terrainHeight(x, z) - 0.08);
    }
    positions.needsUpdate = true;
    geometry.computeVertexNormals();
    return geometry;
}

function contourSegments(width, depth, columns, rows, levels) {
    const vertices = [];
    const dx = width / columns;
    const dz = depth / rows;
    const x0 = -width / 2;
    const z0 = -depth / 2;
    const interpolate = (a, b, level) => {
        const range = b.h - a.h;
        const t = Math.abs(range) < 0.0001 ? 0.5 : (level - a.h) / range;
        return new THREE.Vector3(THREE.MathUtils.lerp(a.x, b.x, t), level - 0.025, THREE.MathUtils.lerp(a.z, b.z, t));
    };

    levels.forEach((level) => {
        for (let row = 0; row < rows; row += 1) {
            for (let column = 0; column < columns; column += 1) {
                const x = x0 + column * dx;
                const z = z0 + row * dz;
                const corners = [
                    { x, z, h: terrainHeight(x, z) },
                    { x: x + dx, z, h: terrainHeight(x + dx, z) },
                    { x: x + dx, z: z + dz, h: terrainHeight(x + dx, z + dz) },
                    { x, z: z + dz, h: terrainHeight(x, z + dz) },
                ];
                const crossings = [];
                [[0, 1], [1, 2], [2, 3], [3, 0]].forEach(([a, b]) => {
                    if ((corners[a].h < level) !== (corners[b].h < level)) crossings.push(interpolate(corners[a], corners[b], level));
                });
                if (crossings.length === 2) vertices.push(crossings[0], crossings[1]);
                if (crossings.length === 4) vertices.push(crossings[0], crossings[1], crossings[2], crossings[3]);
            }
        }
    });
    return vertices;
}

function createMapSurfaceMaterial(color, opacity, scanBoost = 0, flowing = false) {
    const baseColor = new THREE.Color(color);
    return registerTerrainMaterial(new THREE.ShaderMaterial({
        uniforms: {
            uColor: { value: baseColor },
            uOpacity: { value: opacity },
            uScanRadius: { value: 0 },
            uTime: { value: 0 },
            uScanBoost: { value: scanBoost },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        vertexShader: `
            varying vec3 vWorldPosition;
            varying vec2 vUv;
            void main() {
                vec4 world = modelMatrix * vec4(position, 1.0);
                vWorldPosition = world.xyz;
                vUv = uv;
                gl_Position = projectionMatrix * viewMatrix * world;
            }
        `,
        fragmentShader: `
            uniform vec3 uColor;
            uniform float uOpacity;
            uniform float uScanRadius;
            uniform float uTime;
            uniform float uScanBoost;
            varying vec3 vWorldPosition;
            varying vec2 vUv;
            void main() {
                float radius = length(vWorldPosition.xz);
                float scan = 1.0 - smoothstep(0.0, 1.0, abs(radius - uScanRadius));
                float flow = ${flowing ? "0.72 + sin(vUv.y * 42.0 - uTime * 1.15) * 0.14" : "1.0"};
                vec3 color = uColor * (flow + scan * uScanBoost);
                float alpha = uOpacity * (1.0 + scan * uScanBoost * 0.7);
                gl_FragColor = vec4(color, alpha);
            }
        `,
    }));
}

function createRoadMaterial() {
    return registerTerrainMaterial(new THREE.ShaderMaterial({
        uniforms: {
            uScanRadius: { value: 0 },
        },
        transparent: false,
        depthWrite: true,
        depthTest: true,
        polygonOffset: true,
        polygonOffsetFactor: -2,
        polygonOffsetUnits: -2,
        vertexShader: `
            varying vec3 vWorldPosition;
            varying vec2 vUv;
            void main() {
                vec4 world = modelMatrix * vec4(position, 1.0);
                vWorldPosition = world.xyz;
                vUv = uv;
                gl_Position = projectionMatrix * viewMatrix * world;
            }
        `,
        fragmentShader: `
            uniform float uScanRadius;
            varying vec3 vWorldPosition;
            varying vec2 vUv;
            void main() {
                float radius = length(vWorldPosition.xz);
                float scan = 1.0 - smoothstep(0.0, 1.0, abs(radius - uScanRadius));
                float edge = smoothstep(0.0, 0.18, vUv.x) * smoothstep(0.0, 0.18, 1.0 - vUv.x);
                vec3 edgeColor = vec3(0.34, 0.105, 0.018);
                vec3 coreColor = vec3(0.92, 0.31, 0.055);
                vec3 color = mix(edgeColor, coreColor, edge);
                color += vec3(0.32, 0.12, 0.025) * scan;
                gl_FragColor = vec4(color, 1.0);
            }
        `,
    }));
}

function createRibbonGeometry(path, width, yOffset = 0.03, samples = 120) {
    const controlPoints = path.map(([x, z]) => new THREE.Vector3(x, terrainHeight(x, z) + yOffset, z));
    const curve = new THREE.CatmullRomCurve3(controlPoints, false, "centripetal", 0.35);
    const positions = [];
    const uvs = [];
    const indices = [];

    for (let i = 0; i <= samples; i += 1) {
        const t = i / samples;
        const point = curve.getPoint(t);
        const tangent = curve.getTangent(t).normalize();
        const side = new THREE.Vector3(-tangent.z, 0, tangent.x).normalize().multiplyScalar(width / 2);
        const left = point.clone().add(side);
        const right = point.clone().sub(side);
        left.y = terrainHeight(left.x, left.z) + yOffset;
        right.y = terrainHeight(right.x, right.z) + yOffset;
        positions.push(left.x, left.y, left.z, right.x, right.y, right.z);
        uvs.push(0, t, 1, t);
        if (i < samples) {
            const start = i * 2;
            indices.push(start, start + 2, start + 1, start + 2, start + 3, start + 1);
        }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
}

function addRibbon(path, width, material, yOffset = 0.03, samples = 120) {
    const mesh = new THREE.Mesh(createRibbonGeometry(path, width, yOffset, samples), material);
    world.add(mesh);
    return mesh;
}

function createRoadNetwork() {
    const arterialMaterial = createRoadMaterial();
    CITY_PATHS.arterials.forEach((path) => {
        addRibbon(path, MAP_CONFIG.roads.arterialWidth, arterialMaterial, 0.052, 100);
    });
}

function createCityBlocks() {
    const blocks = [
        [-13.5, 5.1, 1.8, 0.9, -0.15], [-11, 0.4, 1.5, 0.8, 0.18], [-12.2, -4.4, 1.8, 0.75, -0.12],
        [-8.2, -7.2, 1.45, 0.8, 0.24], [-7.8, 7.8, 1.5, 0.7, -0.24], [-4, 8.7, 1.35, 0.75, 0.18],
        [1.7, 9.2, 1.6, 0.72, -0.1], [6.4, 8, 1.7, 0.8, 0.2], [11.5, 5.8, 1.75, 0.85, -0.16],
        [12.5, 1, 1.45, 0.72, 0.12], [12.1, -4.5, 1.7, 0.86, 0.2], [8.4, -7.4, 1.65, 0.78, -0.22],
        [3.4, -8.7, 1.5, 0.8, 0.08], [-3.4, -8.6, 1.55, 0.76, -0.16], [-7.2, -3.5, 1.25, 0.68, 0.23],
        [-5.8, 3.2, 1.3, 0.65, -0.18], [3.8, 5.4, 1.25, 0.68, 0.16], [7.6, 2.3, 1.4, 0.72, -0.12],
        [7.1, -3.2, 1.35, 0.7, 0.2], [-2.4, 5.8, 1.25, 0.62, -0.16],
    ];
    const blockMaterial = createMapSurfaceMaterial(0x24415f, 0.12, 0.22);
    blocks.forEach(([x, z, width, depth, rotation]) => {
        const block = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), blockMaterial);
        block.rotation.x = -Math.PI / 2;
        block.rotation.z = rotation;
        block.position.set(x, terrainHeight(x, z) + 0.026, z);
        world.add(block);
    });
}

function createGround() {
    const width = 40;
    const depth = 26;
    const ground = new THREE.Mesh(buildTerrainGeometry(width, depth, 150, 96), createTerrainMaterial());
    world.add(ground);

    const contourPoints = contourSegments(width, depth, 112, 72, [-0.42, -0.3, -0.18, -0.06, 0.06, 0.18, 0.3, 0.42, 0.54]);
    world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(contourPoints), createContourMaterial()));

    createCityBlocks();
    createRoadNetwork();
}

function createStars() {
    const count = 850;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const cyan = new THREE.Color(COLORS.cyan);
    const violet = new THREE.Color(COLORS.violet);
    for (let i = 0; i < count; i += 1) {
        const radius = 12 + Math.random() * 42;
        const angle = Math.random() * Math.PI * 2;
        positions[i * 3] = Math.cos(angle) * radius;
        positions[i * 3 + 1] = Math.random() * 13 - 1;
        positions[i * 3 + 2] = Math.sin(angle) * radius;
        const color = Math.random() > 0.72 ? violet : cyan;
        colors.set([color.r, color.g, color.b], i * 3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const particles = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.055, transparent: true, opacity: 0.52, vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    particles.name = "stars";
    world.add(particles);
}

function createNode(config) {
    const group = new THREE.Group();
    const color = config.type === "core" ? COLORS.cyan : config.type === "relay" ? COLORS.violet : 0x67c9ef;
    const baseRadius = config.type === "core" ? 1.08 : config.type === "relay" ? 0.55 : 0.34;

    const disc = new THREE.Mesh(new THREE.CylinderGeometry(baseRadius, baseRadius * 1.14, 0.12, config.type === "relay" ? 6 : 32), material(color, 0.3));
    disc.position.y = 0.08;
    group.add(disc);

    const beaconHeight = config.type === "core" ? 2.9 : config.type === "relay" ? 1.45 : 0.72;
    const beacon = new THREE.Mesh(new THREE.CylinderGeometry(baseRadius * 0.09, baseRadius * 0.34, beaconHeight, config.type === "relay" ? 6 : 16, 1, true), material(color, 0.35));
    beacon.position.y = beaconHeight / 2 + 0.12;
    group.add(beacon);

    const orb = new THREE.Mesh(new THREE.SphereGeometry(baseRadius * (config.type === "core" ? 0.27 : 0.2), 16, 12), material(config.type === "core" ? COLORS.white : color));
    orb.position.y = beaconHeight + 0.16;
    group.add(orb);

    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeGlowTexture(), color, transparent: true, opacity: config.type === "core" ? 0.9 : 0.65, blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.scale.setScalar(baseRadius * (config.type === "core" ? 5.2 : 3.8));
    glow.position.y = beaconHeight + 0.1;
    group.add(glow);

    const ringCount = config.type === "core" ? 3 : config.type === "relay" ? 2 : 1;
    const rotating = [];
    for (let i = 0; i < ringCount; i += 1) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(baseRadius * (1.15 + i * 0.34), 0.018 + i * 0.006, 6, 64), material(i === 1 ? COLORS.violet : color, 0.62 - i * 0.1));
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 0.12 + i * 0.12;
        rotating.push(ring);
        group.add(ring);
    }

    const label = document.createElement("div");
    label.className = `node-label ${config.type}`;
    label.innerHTML = `<span class="name">${config.name}</span><span class="value"><b>${config.volume}</b><small>${config.type === "relay" ? "LOAD" : "PKG"}</small></span>`;
    labelLayer.appendChild(label);
    label.addEventListener("mouseenter", () => showDetail(config));
    label.addEventListener("mouseleave", hideDetail);

    const node = { ...config, group, orb, glow, rotating, label, displayVolume: config.volume, target: new THREE.Vector3(), lastArrival: "--:--:--", load: 42 + Math.floor(Math.random() * 46) };
    nodes.set(config.id, node);
    world.add(group);
    return node;
}

let glowTexture;
function makeGlowTexture() {
    if (glowTexture) return glowTexture;
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.12, "rgba(180,245,255,.8)");
    gradient.addColorStop(0.38, "rgba(87,166,255,.22)");
    gradient.addColorStop(1, "rgba(0,0,0,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 128, 128);
    glowTexture = new THREE.CanvasTexture(canvas);
    return glowTexture;
}

function applyLayout(force = false) {
    const aspect = window.innerWidth / window.innerHeight;
    const next = aspect >= 1.9 ? "wide" : aspect < 1.25 ? "compact" : "standard";
    currentLayout = next;
    const layout = layouts[next];
    nodes.forEach((node) => {
        const [x, z] = layout[node.id];
        node.target.set(x, terrainHeight(x, z), z);
        if (force) node.group.position.copy(node.target);
    });
    updateCamera(aspect);
    rebuildRoutes();
}

function updateCamera(aspect) {
    if (aspect >= 1.9) {
        camera.position.set(0, 24, 23.5);
        camera.fov = 38;
    } else if (aspect < 1.25) {
        camera.position.set(0, 25.5, 22.5);
        camera.fov = 45;
    } else {
        camera.position.set(0, 23, 22);
        camera.fov = 42;
    }
    camera.lookAt(0, 0, currentLayout === "compact" ? -0.4 : 0.4);
    camera.updateProjectionMatrix();
}

function makeCurve(ids, lift = 2.2) {
    const points = ids.map((id) => nodes.get(id).target.clone());
    const curvePoints = [];
    points.forEach((point, index) => {
        const endpoint = point.clone();
        endpoint.y += index === 0 || index === points.length - 1 ? 0.32 : 0.58;
        curvePoints.push(endpoint);
        if (index < points.length - 1) {
            const midpoint = point.clone().lerp(points[index + 1], 0.5);
            midpoint.y += lift + point.distanceTo(points[index + 1]) * 0.07;
            curvePoints.push(midpoint);
        }
    });
    return new THREE.CatmullRomCurve3(curvePoints, false, "centripetal", 0.4);
}

function rebuildRoutes() {
    routes.forEach((route) => world.remove(route.line));
    routes.length = 0;
    routeConfig.forEach((ids, index) => {
        const curve = makeCurve(ids, 1.7 + (index % 3) * 0.38);
        const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(90));
        const line = new THREE.Line(geometry, lineMaterial(index % 3 === 0 ? COLORS.violet : COLORS.cyan, 0.16));
        world.add(line);
        routes.push({ ids, curve, line });
    });
}

function createFlight(route) {
    const destination = nodes.get(route.ids.at(-1));
    const amount = 1 + Math.floor(Math.random() * 8);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8), material(Math.random() > 0.32 ? COLORS.cyan : COLORS.violet));
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeGlowTexture(), color: Math.random() > 0.32 ? COLORS.cyan : COLORS.violet, transparent: true, opacity: 0.82, blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.scale.setScalar(1.15);
    head.add(glow);
    const trailPoints = Array.from({ length: 13 }, () => new THREE.Vector3());
    const trailGeometry = new THREE.BufferGeometry().setFromPoints(trailPoints);
    const trail = new THREE.Line(trailGeometry, lineMaterial(COLORS.cyan, 0.55));
    world.add(head, trail);
    flights.push({ route, destination, amount, head, trail, progress: 0, speed: 0.16 + Math.random() * 0.08, trailPoints });
    route.line.material.opacity = 0.52;
    updateActiveRoutes();
    const relayName = nodes.get(route.ids[1]).name;
    addEvent(`${relayName} 建立至 <b>${destination.name}</b> 的高速链路`);
}

function completeFlight(flight) {
    world.remove(flight.head, flight.trail);
    flight.head.geometry.dispose();
    flight.trail.geometry.dispose();
    flight.route.line.material.opacity = 0.16;
    flight.destination.volume += flight.amount;
    flight.destination.lastArrival = timeText();
    flight.destination.load = Math.min(99, Math.max(38, flight.destination.load + Math.floor(Math.random() * 9) - 3));
    pulseLabel(flight.destination);
    createShockwave(flight.destination.group.position, flight.destination.type === "relay" ? COLORS.violet : COLORS.cyan);
    addEvent(`物流流抵达 <b>${flight.destination.name}</b>，完成 ${flight.amount} 件包裹调度`);
    const relay = nodes.get(flight.route.ids[1]);
    relay.volume += flight.amount;
    relay.load = Math.min(98, relay.load + 1);
}

function createShockwave(position, color) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.22, 0.28, 40), material(color, 0.78));
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(position);
    ring.position.y += 0.11;
    world.add(ring);
    shockwaves.push({ ring, life: 0 });
}

function updateFlights(delta) {
    for (let i = flights.length - 1; i >= 0; i -= 1) {
        const flight = flights[i];
        flight.progress += delta * flight.speed;
        const progress = Math.min(flight.progress, 1);
        flight.head.position.copy(flight.route.curve.getPoint(progress));
        for (let j = flight.trailPoints.length - 1; j > 0; j -= 1) flight.trailPoints[j].copy(flight.trailPoints[j - 1]);
        flight.trailPoints[0].copy(flight.head.position);
        flight.trail.geometry.setFromPoints(flight.trailPoints);
        flight.trail.material.opacity = Math.sin(progress * Math.PI) * 0.62;
        if (flight.progress >= 1) {
            completeFlight(flight);
            flights.splice(i, 1);
            updateActiveRoutes();
        }
    }
}

function updateShockwaves(delta) {
    for (let i = shockwaves.length - 1; i >= 0; i -= 1) {
        const shockwave = shockwaves[i];
        shockwave.life += delta;
        const scale = 1 + shockwave.life * 4.2;
        shockwave.ring.scale.setScalar(scale);
        shockwave.ring.material.opacity = Math.max(0, 0.72 - shockwave.life * 0.72);
        if (shockwave.life >= 1) {
            world.remove(shockwave.ring);
            shockwave.ring.geometry.dispose();
            shockwaves.splice(i, 1);
        }
    }
}

function updateLabels(delta) {
    nodes.forEach((node) => {
        node.group.position.lerp(node.target, Math.min(1, delta * 3.4));
        node.displayVolume += (node.volume - node.displayVolume) * Math.min(1, delta * 5);
        node.label.querySelector("b").textContent = Math.round(node.displayVolume).toLocaleString("zh-CN");
        const position = node.group.position.clone();
        position.y += node.type === "core" ? 3.3 : node.type === "relay" ? 1.8 : 1.1;
        position.project(camera);
        const x = (position.x * 0.5 + 0.5) * window.innerWidth;
        const y = (-position.y * 0.5 + 0.5) * window.innerHeight;
        node.label.style.left = `${Math.max(55, Math.min(window.innerWidth - 55, x))}px`;
        node.label.style.top = `${Math.max(90, Math.min(window.innerHeight - 45, y))}px`;
        node.label.style.opacity = position.z > 1 ? "0" : "1";
    });
}

function pulseLabel(node) {
    node.label.classList.remove("pulse");
    void node.label.offsetWidth;
    node.label.classList.add("pulse");
}

function updateNodeAnimation(elapsed) {
    nodes.forEach((node, index) => {
        node.rotating.forEach((ring, ringIndex) => {
            ring.rotation.z = elapsed * (0.23 + ringIndex * 0.13) * (index % 2 ? -1 : 1);
        });
        node.orb.scale.setScalar(1 + Math.sin(elapsed * 2.1 + index) * 0.12);
        node.glow.material.opacity = (node.type === "core" ? 0.75 : 0.48) + Math.sin(elapsed * 1.7 + index) * 0.12;
    });
    const stars = world.getObjectByName("stars");
    if (stars) stars.rotation.y = elapsed * 0.008;
}

function updateTerrainScan(elapsed) {
    const { cycleDuration, travelDuration, maxRadius } = MAP_CONFIG.scan;
    const cycle = Math.floor(elapsed / cycleDuration);
    const phase = elapsed % cycleDuration;
    const active = !lowMotion && phase <= travelDuration;
    const scanRadius = active ? THREE.MathUtils.smoothstep(phase / travelDuration, 0, 1) * maxRadius : -100;

    terrainMaterials.forEach((terrainMaterial) => {
        if (terrainMaterial.uniforms.uTime) terrainMaterial.uniforms.uTime.value = elapsed;
        terrainMaterial.uniforms.uScanRadius.value = scanRadius;
    });

    if (active && cycle !== lastScanCycle) {
        lastScanCycle = cycle;
        createShockwave(nodes.get("core").group.position, COLORS.cyan);
        addEvent("SmartStation 启动全域辐射扫描，正在刷新地形链路");
    }

    const core = nodes.get("core");
    const charge = active ? Math.sin(Math.min(phase / 0.9, 1) * Math.PI) : 0;
    core.glow.material.opacity = 0.75 + charge * 0.24;
    coreLight.intensity = 28 + Math.sin(elapsed * 1.9) * 4 + charge * 13;
}

function dispatch(elapsed) {
    if (lowMotion || elapsed < nextDispatchAt || flights.length >= 6) return;
    const route = routes[Math.floor(Math.random() * routes.length)];
    if (!flights.some((flight) => flight.route === route)) createFlight(route);
    nextDispatchAt = elapsed + 1.1 + Math.random() * 1.7;
}

function showDetail(node) {
    const rect = node.label.getBoundingClientRect();
    detail.querySelector(":scope > strong").textContent = node.name;
    detail.querySelector('[data-detail="volume"]').textContent = Math.round(node.volume).toLocaleString("zh-CN");
    detail.querySelector('[data-detail="load"]').textContent = `${node.load}%`;
    detail.querySelector('[data-detail="last"]').textContent = node.lastArrival;
    detail.style.left = `${Math.min(window.innerWidth - 230, rect.right)}px`;
    detail.style.top = `${Math.max(100, Math.min(window.innerHeight - 120, rect.top + rect.height / 2))}px`;
    detail.classList.add("visible");
    detail.setAttribute("aria-hidden", "false");
}

function hideDetail() {
    detail.classList.remove("visible");
    detail.setAttribute("aria-hidden", "true");
}

function updateHud() {
    const destinations = nodeConfig.filter((node) => node.type === "destination").map((node) => nodes.get(node.id));
    const total = destinations.reduce((sum, node) => sum + node.volume, 0);
    nodes.get("core").volume = total;
    document.querySelector("#total-volume").textContent = Math.round(total).toLocaleString("zh-CN");
    efficiencyValue += (Math.random() - 0.48) * 0.18;
    efficiencyValue = Math.max(32.4, Math.min(43.8, efficiencyValue));
    document.querySelector("#efficiency").textContent = `+${efficiencyValue.toFixed(1)}%`;
    document.querySelector("#core-load").textContent = `${68 + Math.floor(Math.random() * 11)}%`;
    document.querySelector("#avg-time").textContent = `${(11.8 + Math.random() * 2.2).toFixed(1)}m`;
    document.querySelector("#relay-flow").textContent = ["station1", "station2", "station3"].reduce((sum, id) => sum + nodes.get(id).volume, 0).toLocaleString("zh-CN");
    document.querySelector("#network-score").textContent = 95 + Math.floor(Math.random() * 3);
}

function updateActiveRoutes() {
    document.querySelector("#active-routes").textContent = new Set(flights.map((flight) => flight.route)).size;
}

function timeText() {
    return new Intl.DateTimeFormat("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
}

function updateClock() {
    const now = new Date();
    document.querySelector("#clock").textContent = timeText();
    document.querySelector("#date").textContent = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
}

function addEvent(message) {
    const list = document.querySelector("#event-list");
    const item = document.createElement("li");
    item.innerHTML = `<time>${timeText()}</time><span>${message}</span>`;
    list.prepend(item);
    while (list.children.length > 5) list.lastElementChild.remove();
}

function onResize() {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    applyLayout();
}

function animate() {
    const delta = Math.min(clock.getDelta(), 0.05);
    const elapsed = clock.elapsedTime;
    dispatch(elapsed);
    updateFlights(delta);
    updateShockwaves(delta);
    updateNodeAnimation(elapsed);
    updateTerrainScan(elapsed);
    updateLabels(delta);
    const parallaxX = pointer.x * 0.42;
    const parallaxY = pointer.y * 0.18;
    camera.position.x += (parallaxX - camera.position.x) * delta * 0.32;
    world.rotation.y += ((pointer.x * 0.008) - world.rotation.y) * delta * 0.65;
    world.rotation.x += ((pointer.y * -0.004) - world.rotation.x) * delta * 0.65;
    camera.lookAt(0, parallaxY, currentLayout === "compact" ? -0.4 : 0.4);
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
}

window.addEventListener("resize", onResize);
window.addEventListener("pointermove", (event) => {
    pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -((event.clientY / window.innerHeight) * 2 - 1);
});
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) clock.getDelta();
});

createGround();
createStars();
nodeConfig.forEach(createNode);
applyLayout(true);
updateClock();
updateHud();
addEvent("SmartStation 城市物流辐射网络已完成拓扑同步");
addEvent("全域中继节点保持在线，调度通道运行稳定");
setInterval(updateClock, 1000);
setInterval(updateHud, 1800);
animate();
