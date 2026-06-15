// Redirect permanente: /bermejo → /campo
import { redirect } from "next/navigation";

export default function BermejoPage() {
  redirect("/campo");
}
