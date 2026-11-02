// Cliente del Cuidado de suscriptores (Admin › Cuidar suscriptores).
// Tipos de §8.2 y rutas de §8.3 de docs/contenido-redes-tecnico.md. Los mensajes a
// los comerciantes (M1..M6) los arma el BACKEND: acá sólo se abre `wa.me` con el
// texto; nunca se manda nada solo.

import { panelJson, type ContentPieceSummary, type SocialConsentResponse } from "@/lib/content";

export type SubscriptionState = "al_dia" | "por_vencer" | "vencido" | "cortesia" | "suspendido" | "sin_plan";

export type SubscriberSummaryResponse = {
  comercio_id: string; nombre: string; slug: string;
  whatsapp: string | null; ciudad_nombre: string | null;
  plan: string | null; plan_nombre: string | null; plan_cortesia: boolean;
  paga_hasta: string | null;
  subscription_state: SubscriptionState | string;
  in_grace: boolean;
  social_consent: SocialConsentResponse;
  pieces: { quota: number; used: number; cycle_start: string | null; cycle_end: string | null; next_scheduled_for: string | null };
  tasks: { due_today: number; overdue: number };
  contact_person: string | null;
  onboarding_started_at: string | null;
};
export type SubscriberListResponse = { items: SubscriberSummaryResponse[]; total: number };

export type SubscriberTaskKind =
  | "welcome" | "profile_check" | "first_offer" | "photo_session" | "first_piece" | "week1_checkin"
  | "piece_delivery" | "photo_refresh" | "monthly_report" | "renewal_before" | "renewal_overdue" | "churn_call";

export type SubscriberTaskResponse = {
  id: string; comercio_id: string; comercio_nombre: string;
  kind: SubscriberTaskKind | string; kind_label: string;
  due_on: string; status: "open" | "done" | "skipped";
  overdue: boolean;
  message_template: "M1" | "M2" | "M3" | "M4" | "M5" | "M6" | null;
  message_text: string | null;
  whatsapp: string | null;
  call_script: string[] | null;
  needs_outcome: boolean;
  piece_id: string | null; report_id: string | null;
  outcome: string | null; done_by: string | null; done_at: string | null;
  auto_closed: boolean;
};
export type SubscriberTaskListResponse = { items: SubscriberTaskResponse[]; total: number };

export type SubscriberReportResponse = {
  id: string; period_start: string; period_end: string;
  data: {
    visits: number; whatsapp: number; directions: number; calls: number; from_social: number;
    terms: string[]; pieces_published: number; offers_approved: number;
  };
};

export type ProfileCheckItem = { key: string; label: string; ok: boolean; auto: boolean };

export type SubscriberDetailResponse = {
  summary: SubscriberSummaryResponse;
  profile_check: ProfileCheckItem[];
  tasks: SubscriberTaskResponse[];
  pieces: ContentPieceSummary[];
  last_report: SubscriberReportResponse | null;
};

export type SubscriberFiltro = "tareas" | "todos" | "por_vencer";
export type SubscriberCuando = "hoy" | "atrasadas" | "semana";

export const listarSuscriptores = (filtro: SubscriberFiltro, ciudadSlug: string | null): Promise<SubscriberListResponse> => {
  const p = new URLSearchParams({ filtro });
  if (ciudadSlug) p.set("ciudad", ciudadSlug);
  return panelJson(`/admin/subscribers?${p.toString()}`, {}, "No se pudieron cargar los suscriptores");
};

export const listarTareas = (cuando: SubscriberCuando): Promise<SubscriberTaskListResponse> =>
  panelJson(`/admin/subscribers/tasks?cuando=${cuando}`, {}, "No se pudieron cargar las tareas");

export const getSuscriptor = (comercioId: string): Promise<SubscriberDetailResponse> =>
  panelJson(`/admin/subscribers/${encodeURIComponent(comercioId)}`, {}, "No se pudo cargar el suscriptor");

export const guardarPerfilSuscriptor = (
  comercioId: string, body: { contact_person?: string | null; notes?: string | null },
): Promise<{ ok: boolean; contact_person: string | null; notes: string | null }> =>
  panelJson(`/admin/subscribers/${encodeURIComponent(comercioId)}/profile`, { method: "PATCH", body }, "No se pudo guardar");

export const iniciarBienvenida = (comercioId: string, force: boolean): Promise<{ created: number; started_at: string }> =>
  panelJson(`/admin/subscribers/${encodeURIComponent(comercioId)}/onboarding`, { method: "POST", body: { force } }, "No se pudo iniciar la bienvenida");

export const cerrarTarea = (taskId: string, sent: boolean, outcome: string | null): Promise<SubscriberTaskResponse> =>
  panelJson(`/admin/subscribers/tasks/${encodeURIComponent(taskId)}/done`, { method: "POST", body: { sent, outcome } }, "No se pudo cerrar la tarea");

export const saltarTarea = (taskId: string, note: string | null): Promise<SubscriberTaskResponse> =>
  panelJson(`/admin/subscribers/tasks/${encodeURIComponent(taskId)}/skip`, { method: "POST", body: { note } }, "No se pudo saltar la tarea");
