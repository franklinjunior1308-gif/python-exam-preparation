import { notFound } from "next/navigation";
import { RequestDetail } from "@/components/RequestDetail";

export default async function RequestDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const requestId = Number(id);
  if (!Number.isInteger(requestId) || requestId < 1) notFound();
  return <RequestDetail requestId={requestId} />;
}
