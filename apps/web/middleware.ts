import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that require authentication
const PROTECTED_PREFIXES = [
  "/dashboard",
  "/profile",
  "/goals",
  "/upload",
  "/history",
  "/analytics",
  "/recommendations",
  "/workout",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtectedRoute = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix)
  );

  // NOTE: localStorage-based auth is handled client-side in AuthProvider.
  // This middleware exists for future server-side token validation.
  // For now it passes through all requests.
  void isProtectedRoute;

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/|$).*)",
  ],
};
