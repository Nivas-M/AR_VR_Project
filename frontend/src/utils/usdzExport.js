import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { USDZExporter } from "three/examples/jsm/exporters/USDZExporter.js";

/**
 * Convert a Three.js Object3D/Scene into an Apple AR Quick Look USDZ ArrayBuffer.
 */
export async function exportSceneToUsdzBuffer(scene) {
  scene.updateMatrixWorld(true);

  // Ensure every mesh uses a MeshStandardMaterial compatible with USDZExporter.
  scene.traverse((obj) => {
    if (obj.isMesh && obj.material && !obj.material.isMeshStandardMaterial) {
      obj.material = new THREE.MeshStandardMaterial({
        color: obj.material.color || new THREE.Color(0xcccccc),
        vertexColors: Boolean(obj.geometry?.attributes?.color),
        roughness: 0.7,
        metalness: 0.05,
      });
    }
  });

  const exporter = new USDZExporter();
  return exporter.parseAsync(scene, {
    quickLookCompatible: true,
    includeAnchoringProperties: true,
  });
}

/**
 * Convert a Three.js Object3D/Scene into an Apple AR Quick Look USDZ Blob.
 */
export async function exportSceneToUsdzBlob(scene) {
  const arrayBuffer = await exportSceneToUsdzBuffer(scene);
  return new Blob([arrayBuffer], { type: "model/vnd.usdz+zip" });
}

/**
 * Fetch a metric .glb asset in the browser and convert it client-side to a .usdz Object URL.
 */
export async function convertGlbUrlToUsdzBlobUrl(glbUrl) {
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(glbUrl);
  const blob = await exportSceneToUsdzBlob(gltf.scene);
  return URL.createObjectURL(blob);
}
