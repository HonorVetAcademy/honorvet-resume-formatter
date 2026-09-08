const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface RightSourcingExperience {
  facility_name: string; city: string; state: string;
  start_date: string; end_date: string; job_title: string;
  emr: string; position_type: string; agency_name: string;
  trauma_level: string; facility_type: string;
  additional_details: { label: string; value: string }[];
  duties: string[];
}

export interface RightSourcingResume {
  full_name: string; credentials_suffix?: string; professional_headline?: string;
  phone?: string; email?: string; permanent_address?: string;
  professional_summary: string[];
  core_qualifications: string[];
  education: { degree: string; school: string; location: string; date: string }[];
  licenses: { name: string; id?: string; expires?: string }[];
  certifications: { name: string; id?: string; expires?: string }[];
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
