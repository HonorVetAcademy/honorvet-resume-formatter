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
  downloadUrl: (filename: string) => `${API_URL}/api/download/${filename}`,
};
