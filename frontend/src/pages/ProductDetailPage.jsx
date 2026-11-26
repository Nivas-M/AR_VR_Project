import { useParams } from "react-router-dom";

export default function ProductDetailPage() {
  const { id } = useParams();
  return (
    <section className="ts-page-card">
      <h1>Product Detail: {id}</h1>
    </section>
  );
}
