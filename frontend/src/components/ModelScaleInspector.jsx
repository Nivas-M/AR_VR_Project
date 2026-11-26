import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Box, DoorOpen, RotateCcw, Ruler, Table, User } from "lucide-react";
import { formatDimensions } from "../api/client";

function createHumanSilhouette(material) {
  const group = new THREE.Group();
  group.name = "ref_human_175cm";

  // Legs (0 -> 0.85 m)
  const legGeo = new THREE.CylinderGeometry(0.065, 0.055, 0.85, 12);
  const leftLeg = new THREE.Mesh(legGeo, material);
  leftLeg.position.set(-0.09, 0.425, 0);
  const rightLeg = new THREE.Mesh(legGeo, material);
  rightLeg.position.set(0.09, 0.425, 0);

  // Torso (0.85 -> 1.48 m)
  const torsoGeo = new THREE.CylinderGeometry(0.16, 0.14, 0.63, 14);
  const torso = new THREE.Mesh(torsoGeo, material);
  torso.position.set(0, 1.165, 0);

  // Head (1.48 -> 1.75 m)
  const headGeo = new THREE.SphereGeometry(0.115, 16, 16);
  const head = new THREE.Mesh(headGeo, material);
  head.position.set(0, 1.635, 0);

  group.add(leftLeg, rightLeg, torso, head);
  return group;
}

function createDoorframe(material) {
  const group = new THREE.Group();
  group.name = "ref_doorframe_200cm";
  const frameThickness = 0.08;
  const doorWidth = 0.9;
  const doorHeight = 2.0;

  const postGeo = new THREE.BoxGeometry(frameThickness, doorHeight, frameThickness);
  const leftPost = new THREE.Mesh(postGeo, material);
  leftPost.position.set(-doorWidth / 2, doorHeight / 2, 0);
  const rightPost = new THREE.Mesh(postGeo, material);
  rightPost.position.set(doorWidth / 2, doorHeight / 2, 0);

  const lintelGeo = new THREE.BoxGeometry(doorWidth + frameThickness, frameThickness, frameThickness);
  const lintel = new THREE.Mesh(lintelGeo, material);
  lintel.position.set(0, doorHeight - frameThickness / 2, 0);

  group.add(leftPost, rightPost, lintel);
  return group;
}

function createDeskReference(material) {
  const group = new THREE.Group();
  group.name = "ref_desk_75cm";
  const deskW = 1.2;
  const deskH = 0.75;
  const deskD = 0.6;

  const topGeo = new THREE.BoxGeometry(deskW, 0.04, deskD);
  const top = new THREE.Mesh(topGeo, material);
  top.position.set(0, deskH - 0.02, 0);

  const legGeo = new THREE.BoxGeometry(0.05, deskH - 0.04, 0.05);
  const offsets = [
    [-deskW / 2 + 0.05, -deskD / 2 + 0.05],
    [deskW / 2 - 0.05, -deskD / 2 + 0.05],
    [-deskW / 2 + 0.05, deskD / 2 - 0.05],
    [deskW / 2 - 0.05, deskD / 2 - 0.05],
  ];
  for (const [lx, lz] of offsets) {
    const leg = new THREE.Mesh(legGeo, material);
    leg.position.set(lx, (deskH - 0.04) / 2, lz);
    group.add(leg);
  }
  group.add(top);
  return group;
}

export default function ModelScaleInspector({ modelUrl, scaleReport, title }) {
  const containerRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const boundsRef = useRef({ w: 0.8, h: 0.8, d: 0.8 });

  const [showWireframe, setShowWireframe] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [showPerson, setShowPerson] = useState(true);
  const [showDoorframe, setShowDoorframe] = useState(false);
  const [showDesk, setShowDesk] = useState(false);

  const [loadState, setLoadState] = useState("idle");
  const [webglError, setWebglError] = useState(null);
  const [measuredBox, setMeasuredBox] = useState(null);

  const refsMap = useRef({
    bboxHelper: null,
    gridHelper: null,
    person: null,
    doorframe: null,
    desk: null,
  });

  const resetCamera = () => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const { w, h, d } = boundsRef.current;
    const span = Math.max(w, h, d, 0.6);
    camera.position.set(span * 1.8, Math.max(h * 1.15, 0.9), span * 2.1);
    controls.target.set(0, h * 0.45, 0);
    controls.update();
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !modelUrl) return;

    let animationId = 0;
    let disposed = false;
    let renderer = null;
    let controls = null;

    setLoadState("loading");
    setWebglError(null);

    try {
      const width = container.clientWidth || 640;
      const height = container.clientHeight || 420;

      const scene = new THREE.Scene();
      scene.background = new THREE.Color("#f1f5f9");

      const camera = new THREE.PerspectiveCamera(45, width / height, 0.02, 50);
      camera.position.set(1.8, 1.35, 2.2);
      cameraRef.current = camera;

      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      container.innerHTML = "";
      container.appendChild(renderer.domElement);

      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.target.set(0, 0.4, 0);
      controlsRef.current = controls;

      // Studio lighting
      scene.add(new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 1.25));
      const keyLight = new THREE.DirectionalLight(0xffffff, 1.1);
      keyLight.position.set(3, 5, 4);
      scene.add(keyLight);
      const fillLight = new THREE.DirectionalLight(0xe2e8f0, 0.55);
      fillLight.position.set(-3, 2, -3);
      scene.add(fillLight);

      // Metric floor grid (4m x 4m, 0.1m minor cells)
      const grid = new THREE.GridHelper(4, 40, 0x64748b, 0xcbd5e1);
      grid.visible = showGrid;
      scene.add(grid);
      refsMap.current.gridHelper = grid;

      // Virtual Room Reference props
      const refMat = new THREE.MeshStandardMaterial({
        color: 0x64748b,
        transparent: true,
        opacity: 0.34,
        roughness: 0.7,
      });
      const person = createHumanSilhouette(refMat);
      const doorframe = createDoorframe(refMat);
      const desk = createDeskReference(refMat);
      person.visible = showPerson;
      doorframe.visible = showDoorframe;
      desk.visible = showDesk;
      scene.add(person, doorframe, desk);
      refsMap.current.person = person;
      refsMap.current.doorframe = doorframe;
      refsMap.current.desk = desk;

      const loader = new GLTFLoader();
      loader.load(
        modelUrl,
        (gltf) => {
          if (disposed) return;
          const model = gltf.scene;
          scene.add(model);

          const box = new THREE.Box3().setFromObject(model);
          const size = new THREE.Vector3();
          box.getSize(size);
          boundsRef.current = { w: size.x, h: size.y, d: size.z };
          setMeasuredBox({
            width: size.x,
            height: size.y,
            depth: size.z,
            minY: box.min.y,
          });

          const helper = new THREE.Box3Helper(box, 0x2563eb);
          helper.visible = showWireframe;
          scene.add(helper);
          refsMap.current.bboxHelper = helper;

          // Position room references cleanly around the product
          person.position.set(-(size.x * 0.5 + 0.55), 0, 0);
          doorframe.position.set(0, 0, -(size.z * 0.5 + 0.7));
          desk.position.set(size.x * 0.5 + 0.85, 0, 0);

          resetCamera();
          setLoadState("ready");
        },
        undefined,
        (err) => {
          if (disposed) return;
          setLoadState("error");
          setWebglError(err?.message || "Failed to load .glb model");
        }
      );

      const handleResize = () => {
        if (!container || !renderer) return;
        const w = container.clientWidth || 640;
        const h = container.clientHeight || 420;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener("resize", handleResize);

      const animate = () => {
        if (disposed) return;
        animationId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      };
      animate();

      return () => {
        disposed = true;
        cancelAnimationFrame(animationId);
        window.removeEventListener("resize", handleResize);
        controls?.dispose();
        renderer?.dispose();
      };
    } catch (err) {
      setLoadState("fallback");
      setWebglError(err?.message || "WebGL preview unavailable in this environment");
      return () => {
        disposed = true;
      };
    }
  }, [modelUrl]);

  useEffect(() => {
    if (refsMap.current.bboxHelper) refsMap.current.bboxHelper.visible = showWireframe;
    if (refsMap.current.gridHelper) refsMap.current.gridHelper.visible = showGrid;
    if (refsMap.current.person) refsMap.current.person.visible = showPerson;
    if (refsMap.current.doorframe) refsMap.current.doorframe.visible = showDoorframe;
    if (refsMap.current.desk) refsMap.current.desk.visible = showDesk;
  }, [showWireframe, showGrid, showPerson, showDoorframe, showDesk]);

  const activeDims = measuredBox || scaleReport?.bounding_box_m;
  const formatted = formatDimensions(activeDims);

  return (
    <div className="ts-inspector-card">
      <div className="ts-inspector-toolbar">
        <div>
          <h3>{title || "3D True-Scale Metric Inspector"}</h3>
          <p className="ts-muted">1.0 glTF unit = 1.0 meter • Floor grounded at Y = 0</p>
        </div>

        <div className="ts-toggle-row" role="group" aria-label="3D inspector reference overlays">
          <button
            type="button"
            className={`ts-chip ${showWireframe ? "active" : ""}`}
            onClick={() => setShowWireframe((v) => !v)}
          >
            <Box size={14} /> Bounding Box
          </button>
          <button
            type="button"
            className={`ts-chip ${showGrid ? "active" : ""}`}
            onClick={() => setShowGrid((v) => !v)}
          >
            <Ruler size={14} /> 10 cm Grid
          </button>
          <button
            type="button"
            className={`ts-chip ${showPerson ? "active" : ""}`}
            onClick={() => setShowPerson((v) => !v)}
          >
            <User size={14} /> 175 cm Person
          </button>
          <button
            type="button"
            className={`ts-chip ${showDoorframe ? "active" : ""}`}
            onClick={() => setShowDoorframe((v) => !v)}
          >
            <DoorOpen size={14} /> 200 cm Doorframe
          </button>
          <button
            type="button"
            className={`ts-chip ${showDesk ? "active" : ""}`}
            onClick={() => setShowDesk((v) => !v)}
          >
            <Table size={14} /> 75 cm Desk
          </button>
          <button type="button" className="ts-chip" onClick={resetCamera}>
            <RotateCcw size={14} /> Reset View
          </button>
        </div>
      </div>

      <div className="ts-viewport-wrap">
        <div ref={containerRef} className="ts-three-canvas" data-testid="three-inspector-canvas" />

        {formatted && (
          <div className="ts-dimension-hud" aria-label="Measured 3D dimensions">
            <span className="ts-hud-badge">{formatted.cmLabel}</span>
            <span className="ts-hud-sub">{formatted.inLabel}</span>
            <span className="ts-hud-sub">{formatted.mLabel}</span>
          </div>
        )}

        {loadState === "loading" && !webglError && (
          <div className="ts-viewport-overlay">Loading True-Scale .glb mesh...</div>
        )}

        {webglError && (
          <div className="ts-viewport-overlay ts-viewport-fallback">
            <p>{webglError}</p>
            {formatted && <p>Verified .glb Dimensions: {formatted.cmLabel}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
