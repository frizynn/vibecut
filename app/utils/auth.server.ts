import { auth } from "~/lib/auth.server";

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  image: string | null;
};

// Local single-user mode: no login. Mirrors the backend's LOCAL_MODE so the
// whole app runs as one implicit local user (same id as backend LOCAL_USER_ID).
export const LOCAL_MODE =
  (process.env.LOCAL_MODE ?? "true").trim().toLowerCase() !== "false";

const LOCAL_USER: SessionUser = {
  id: "local-user",
  email: "local@kimu.app",
  name: "Local",
  image: null,
};

export async function requireUser(request: Request): Promise<SessionUser | null> {
  if (LOCAL_MODE) return LOCAL_USER;
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return null;
  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
    image: session.user.image ?? null,
  };
}
