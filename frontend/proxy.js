import { NextResponse } from "next/server";
import { getAuth0 } from "./src/lib/auth0";

export async function proxy(request) {
  const auth0 = getAuth0();
  if (!auth0) return NextResponse.next();
  return auth0.middleware(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icons.svg|robots.txt|sitemap.xml).*)"],
};
