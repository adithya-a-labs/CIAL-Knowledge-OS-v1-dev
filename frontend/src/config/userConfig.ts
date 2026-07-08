import { User } from '../types';

// TODO: Replace with real auth session from Microsoft Entra ID / Keycloak
export const CURRENT_USER: User = {
  name: 'Ananya Nair',
  role: 'admin',
  department: 'Engineering Dept.',
  avatar: null,
  initials: 'AN',
  notificationsCount: 3
};
