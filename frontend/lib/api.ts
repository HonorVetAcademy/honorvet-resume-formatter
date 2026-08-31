const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface FormattedExperience {
  facility_name: string; city: string; state: string;
  start_date: string; end_date: string; job_title: string;
  patient_ratio?: string; duties: string[];
  type_of_facility?: string | null; trauma_level?: string | null;
  bed_size?: string | number | null; emr_system?: string | null;
  research_confidence?: 'high' | 'medium' | 'low'; research_sources?: string[];
}

export interface FormattedResume {
  full_name: string; credentials_suffix?: string; phone?: string; email?: string; location?: string;
  professional_summary: string[];
  education: { degree: string; school: string; location: string; date: string }[];
  certifications: { name: string; issuer: string; id?: string; expires?: string }[];
  experience: FormattedExperience[];
}

export interface FormattedResumeResult { resume: FormattedResume; download_filename: string; }

export interface RightSourcingExperience {
  facility_name: string; city: string; state: string;
  start_date: string; end_date: string; job_title: string;
  emr_mentioned?: string; duties: string[];
  facility_type?: string | null; trauma_level?: string | null; emr_system?: string | null;
  emr_matches_resume?: boolean; position_type?: string; agency_name?: string;
  research_confidence?: 'high' | 'medium' | 'low'; research_sources?: string[];
}

export interface RightSourcingResume {
  full_name: string; credentials_suffix?: string; phone?: string; email?: string; permanent_address?: string;
  professional_summary: string[];
  skills: string[];
  education: { degree: string; school: string; location: string; date: string }[];
  certifications: { name: string; issuer: string; id?: string; expires?: string }[];
  experience: RightSourcingExperience[];
}

export interface ChecklistItem {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'warning' | 'info';
  detail: string;
}

export interface RightSourcingResult {
  resume: RightSourcingResume;
  checklist: ChecklistItem[];
  download_filename: string;
}

export const api = {
  format: (file: File) => {
    const fd = new FormData();
    fd.append('resume', file);
    return fetch(`${API_URL}/api/format`, { method: 'POST', body: fd })
      .then(async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: r.statusText }));
          throw new Error(err.detail || 'Request failed');
        }
        return r.json() as Promise<FormattedResumeResult>;
      });
  },
  formatRightSourcing: (file: File) => {
    const fd = new FormData();
    fd.append('resume', file);
    return fetch(`${API_URL}/api/rightsourcing/format`, { method: 'POST', body: fd })
      .then(async r => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: r.statusText }));
          throw new Error(err.detail || 'Request failed');
        }
        return r.json() as Promise<RightSourcingResult>;
      });
  },
  downloadUrl: (filename: string) => `${API_URL}/api/download/${filename}`,
};
