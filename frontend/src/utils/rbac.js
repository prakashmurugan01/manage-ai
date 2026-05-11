export const ROLES = {
  SUPER_ADMIN: "SUPER_ADMIN",
  ADMIN: "ADMIN",
  DEVELOPER: "DEVELOPER",
  CLIENT: "CLIENT"
};

export const ROLE_LABELS = {
  [ROLES.SUPER_ADMIN]: "Super Admin",
  [ROLES.ADMIN]: "Admin",
  [ROLES.DEVELOPER]: "Developer",
  [ROLES.CLIENT]: "Client"
};

export function hasAnyRole(user, roles = []) {
  if (!roles.length) return true;
  return Boolean(user && roles.includes(user.role));
}

export function canManage(user) {
  return hasAnyRole(user, [ROLES.SUPER_ADMIN, ROLES.ADMIN]);
}

export function canViewSystem(user) {
  return hasAnyRole(user, [ROLES.SUPER_ADMIN]);
}
