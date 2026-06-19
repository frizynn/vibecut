import { betterAuth } from "better-auth";
import { Pool } from "pg";

// Mirrors the LOCAL_MODE flag in app/utils/auth.server.ts and the backend.
// Inlined (not imported from ~/utils/auth.server) to avoid a circular import:
// utils/auth.server.ts imports `auth` from this module.
const LOCAL_MODE =
  (process.env.LOCAL_MODE ?? "true").trim().toLowerCase() !== "false";

function createPgAuth() {
  return betterAuth({
    database: new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: process.env.DATABASE_SSL === "true" ? { rejectUnauthorized: false } : false,
      connectionTimeoutMillis: 5000,
    }),
    baseURL: process.env.BETTER_AUTH_URL,
    secret: process.env.BETTER_AUTH_SECRET,
    socialProviders: {
      google: {
        clientId: process.env.GOOGLE_CLIENT_ID as string,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
      },
    },
    advanced: {
      database: {
        generateId: "uuid",
      },
    },
  });
}

type Auth = ReturnType<typeof createPgAuth>;

// In LOCAL_MODE there is no login: requireUser() short-circuits before ever
// touching `auth`, and the /api/auth.$ routes are never hit (no login UI). The
// stub satisfies the two members consumers actually use (`handler`,
// `api.getSession`) without constructing a pg Pool, so the SSR server boots
// with zero Postgres. It is typed as `Auth` so both branches share one type.
function createLocalAuthStub(): Auth {
  const stub = {
    handler: async (_request: Request): Promise<Response> =>
      new Response("Auth disabled in LOCAL_MODE", { status: 404 }),
    api: {
      getSession: async (): Promise<null> => null,
    },
  };
  return stub as unknown as Auth;
}

export const auth: Auth = LOCAL_MODE ? createLocalAuthStub() : createPgAuth();
