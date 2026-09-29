import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// HTTP Basic Auth for the whole dashboard when DASHBOARD_PASSWORD is set.
// The pages show account data (cards, values, lineups, ranks), so a hosted
// instance must never be open. Unset locally for `npm run dev`.
export function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return NextResponse.next();

  const user = process.env.DASHBOARD_USER ?? "nick";
  const header = request.headers.get("authorization") ?? "";
  if (header.startsWith("Basic ")) {
    try {
      const [u, ...rest] = atob(header.slice(6)).split(":");
      if (u === user && rest.join(":") === password) return NextResponse.next();
    } catch {
      // malformed header -> challenge again
    }
  }
  return new NextResponse("Anmeldung erforderlich", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="sorarebuddy", charset="UTF-8"' },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
