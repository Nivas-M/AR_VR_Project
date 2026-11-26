import { useParams } from "react-router-dom";

export default function ArViewerPage() {
  const { id } = useParams();
  return (
    <section className="ts-page-card">
      <h1>True-Scale AR Placement Viewer: {id}</h1>
    </section>
  );
}
