export const ROLES = ["customer", "dispatcher", "admin", "technician"] as const;
export type Role = (typeof ROLES)[number];

export const STATUSES = [
  "SUBMITTED",
  "TRIAGED",
  "SCHEDULED",
  "ACCEPTED",
  "IN_PROGRESS",
  "BLOCKED",
  "COMPLETED",
  "CLOSED",
  "CANCELED",
  "REOPENED",
] as const;
export type RequestStatus = (typeof STATUSES)[number];

export const PRIORITIES = ["LOW", "NORMAL", "HIGH"] as const;
export type Priority = (typeof PRIORITIES)[number];

export type Membership = {
  organization_id: number;
  organization_name: string;
  timezone: string;
  role: Role;
};

export type Me = { id: number; email: string; full_name: string; memberships: Membership[] };

export type ServiceRequest = {
  id: number;
  organization_id: number;
  title: string;
  description: string;
  category_id: number;
  property_id: number;
  asset_id: number | null;
  priority: Priority;
  status: RequestStatus;
  desired_start: string | null;
  desired_end: string | null;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
  allowed_actions: RequestStatus[];
};

export type RequestPage = {
  items: ServiceRequest[];
  total: number;
  page: number;
  page_size: number;
};

export type HistoryEntry = {
  id: number;
  from_status: RequestStatus | null;
  to_status: RequestStatus;
  actor_user_id: number;
  reason: string | null;
  created_at: string;
};

export type Category = {
  id: number;
  name: string;
  description: string;
  default_duration_min: number;
  is_active: boolean;
};
export type Property = { id: number; name: string; address: string; is_active: boolean };
export type Asset = {
  id: number;
  property_id: number;
  code: string;
  name: string;
  asset_type: string;
  status: string;
};

export const ASSIGNMENT_STATUSES = [
  "SCHEDULED",
  "ACCEPTED",
  "IN_PROGRESS",
  "BLOCKED",
  "COMPLETED",
  "CANCELED",
  "DECLINED",
] as const;
export type AssignmentStatus = (typeof ASSIGNMENT_STATUSES)[number];

export type Technician = {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  skills: string[];
  availability: { weekday: number; start_time: string; end_time: string }[];
  load_percent: number;
};

export type Assignment = {
  id: number;
  request_id: number;
  request_title: string;
  technician_id: number;
  technician_name: string;
  start_at: string;
  end_at: string;
  timezone: string;
  status: AssignmentStatus;
};

export type Suggestion = {
  technician_id: number;
  full_name: string;
  skills: string[];
  start_at: string;
  end_at: string;
  load_percent: number;
  within_desired_window: boolean | null;
  is_best: boolean;
};

export type Candidate = {
  technician_id: number;
  full_name: string;
  skills: string[];
  available: boolean;
  load_percent: number;
  reasons: { code: string; detail: string | null }[];
  conflicting_assignment_ids: number[];
};

export type Schedule = {
  timezone: string;
  technicians: Technician[];
  assignments: Assignment[];
  absences: { technician_id: number; start_at: string; end_at: string; reason: string | null }[];
};

export type Summary = {
  total: number;
  open: number;
  in_progress: number;
  completed_in_period: number;
  period_days: number;
  timezone: string;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_category: { category_id: number; name: string; count: number }[];
  daily: { date: string; created: number; completed: number }[];
};
