import { Container } from "@/shared/ui/container";
import { HealthStatus } from "@/features/health";

export default function HomePage() {
  return (
    <Container>
      <h1>Root Frontend</h1>
      <p>Simple and scalable starter structure with Next.js App Router.</p>
      <HealthStatus />
    </Container>
  );
}
