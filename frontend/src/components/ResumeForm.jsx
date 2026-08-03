import React, { useState, useEffect } from 'react';

const defaultData = {
  name: '', email: '', phone: '', location: '', linkedin: '', github: '', portfolio: '',
  raw_summary: '', skills: '',
  education: [{ degree: '', institution: '', location: '', start_year: '', end_year: '', grade: '' }],
  experience: [],
  projects: [{ title: '', description: '', tech_stack: '', link: '' }],
  certifications: [],
  achievements: ''
};

const ResumeForm = ({ prefix, onDataChange, initialData }) => {
  const [formData, setFormData] = useState(initialData || defaultData);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    onDataChange(formData);
    validateForm(formData);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleArrayChange = (section, index, field, value) => {
    setFormData(prev => {
      const newArray = [...prev[section]];
      newArray[index] = { ...newArray[index], [field]: value };
      return { ...prev, [section]: newArray };
    });
  };

  const addArrayItem = (section, defaultItem) => {
    setFormData(prev => ({
      ...prev,
      [section]: [...prev[section], defaultItem]
    }));
  };

  const removeArrayItem = (section, index) => {
    setFormData(prev => ({
      ...prev,
      [section]: prev[section].filter((_, i) => i !== index)
    }));
  };

  const validateForm = (data) => {
    const newErrors = {};
    if (!data.name || data.name.length < 2) newErrors.name = 'Name must be at least 2 characters';
    if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) newErrors.email = 'Invalid email';
    if (!data.phone || !/^\d{10,15}$/.test(data.phone)) newErrors.phone = 'Phone must be 10-15 digits';
    
    const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/i;
    if (data.linkedin && !urlPattern.test(data.linkedin)) newErrors.linkedin = 'Invalid URL';
    if (data.github && !urlPattern.test(data.github)) newErrors.github = 'Invalid URL';
    if (data.portfolio && !urlPattern.test(data.portfolio)) newErrors.portfolio = 'Invalid URL';
    
    if (!data.skills || data.skills.trim().length === 0) newErrors.skills = 'Skills are required';

    data.education.forEach((edu, i) => {
      if (!edu.degree) newErrors[`edu_degree_${i}`] = 'Required';
      if (!edu.institution) newErrors[`edu_inst_${i}`] = 'Required';
      if (!edu.start_year || !/^(\d{4}|present)$/i.test(edu.start_year)) newErrors[`edu_start_${i}`] = 'Invalid year';
      if (!edu.end_year || !/^(\d{4}|present)$/i.test(edu.end_year)) newErrors[`edu_end_${i}`] = 'Invalid year';
    });

    data.projects.forEach((proj, i) => {
      if (!proj.title) newErrors[`proj_title_${i}`] = 'Required';
      if (!proj.description) newErrors[`proj_desc_${i}`] = 'Required';
      if (!proj.tech_stack) newErrors[`proj_tech_${i}`] = 'Required';
    });
    
    data.experience.forEach((exp, i) => {
      if (!exp.role) newErrors[`exp_role_${i}`] = 'Required';
      if (!exp.company) newErrors[`exp_company_${i}`] = 'Required';
      if (!exp.start_date) newErrors[`exp_start_${i}`] = 'Required';
      if (!exp.end_date) newErrors[`exp_end_${i}`] = 'Required';
      if (!exp.responsibilities) newErrors[`exp_resp_${i}`] = 'Required';
    });

    data.certifications.forEach((cert, i) => {
      if (!cert.name) newErrors[`cert_name_${i}`] = 'Required';
    });

    setErrors(newErrors);
  };

  return (
    <div className="resume-form">
      {/* 1. Personal Information */}
      <div className="form-section">
        <h3 className="section-title">Personal Information</h3>
        <div className="form-row">
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">Name *</label>
              <input type="text" className="field-input" value={formData.name} onChange={e => handleChange('name', e.target.value)} />
              {errors.name && <span className="field-error">{errors.name}</span>}
            </div>
          </div>
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">Email *</label>
              <input type="email" className="field-input" value={formData.email} onChange={e => handleChange('email', e.target.value)} />
              {errors.email && <span className="field-error">{errors.email}</span>}
            </div>
          </div>
        </div>
        
        <div className="form-row">
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">Phone *</label>
              <input type="text" className="field-input" value={formData.phone} onChange={e => handleChange('phone', e.target.value)} />
              {errors.phone && <span className="field-error">{errors.phone}</span>}
            </div>
          </div>
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">Location</label>
              <input type="text" className="field-input" value={formData.location} onChange={e => handleChange('location', e.target.value)} />
            </div>
          </div>
        </div>

        <div className="form-row">
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">LinkedIn</label>
              <input type="text" className="field-input" value={formData.linkedin} onChange={e => handleChange('linkedin', e.target.value)} />
              {errors.linkedin && <span className="field-error">{errors.linkedin}</span>}
            </div>
          </div>
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">GitHub</label>
              <input type="text" className="field-input" value={formData.github} onChange={e => handleChange('github', e.target.value)} />
              {errors.github && <span className="field-error">{errors.github}</span>}
            </div>
          </div>
        </div>
        
        <div className="form-row">
          <div className="form-col">
            <div className="field-group">
              <label className="field-label">Portfolio</label>
              <input type="text" className="field-input" value={formData.portfolio} onChange={e => handleChange('portfolio', e.target.value)} />
              {errors.portfolio && <span className="field-error">{errors.portfolio}</span>}
            </div>
          </div>
        </div>
        
        <div className="field-group">
          <label className="field-label">Professional Summary</label>
          <textarea className="field-textarea" value={formData.raw_summary} onChange={e => handleChange('raw_summary', e.target.value)} />
        </div>
      </div>

      {/* 2. Skills */}
      <div className="form-section">
        <h3 className="section-title">Skills</h3>
        <div className="field-group">
          <label className="field-label">Skills (comma separated) *</label>
          <textarea className="field-textarea" value={formData.skills} onChange={e => handleChange('skills', e.target.value)} />
          {errors.skills && <span className="field-error">{errors.skills}</span>}
        </div>
      </div>

      {/* 3. Education */}
      <div className="form-section repeatable-section">
        <h3 className="section-title">Education *</h3>
        {formData.education.map((edu, index) => (
          <div key={`${prefix}-edu-${index}`} className="repeatable-item">
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Degree *</label>
                  <input type="text" className="field-input" value={edu.degree} onChange={e => handleArrayChange('education', index, 'degree', e.target.value)} />
                  {errors[`edu_degree_${index}`] && <span className="field-error">{errors[`edu_degree_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Institution *</label>
                  <input type="text" className="field-input" value={edu.institution} onChange={e => handleArrayChange('education', index, 'institution', e.target.value)} />
                  {errors[`edu_inst_${index}`] && <span className="field-error">{errors[`edu_inst_${index}`]}</span>}
                </div>
              </div>
            </div>
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Start Year *</label>
                  <input type="text" className="field-input" value={edu.start_year} onChange={e => handleArrayChange('education', index, 'start_year', e.target.value)} />
                  {errors[`edu_start_${index}`] && <span className="field-error">{errors[`edu_start_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">End Year *</label>
                  <input type="text" className="field-input" value={edu.end_year} onChange={e => handleArrayChange('education', index, 'end_year', e.target.value)} />
                  {errors[`edu_end_${index}`] && <span className="field-error">{errors[`edu_end_${index}`]}</span>}
                </div>
              </div>
            </div>
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Location</label>
                  <input type="text" className="field-input" value={edu.location} onChange={e => handleArrayChange('education', index, 'location', e.target.value)} />
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Grade/GPA</label>
                  <input type="text" className="field-input" value={edu.grade} onChange={e => handleArrayChange('education', index, 'grade', e.target.value)} />
                </div>
              </div>
            </div>
            {formData.education.length > 1 && (
              <button type="button" className="remove-btn" onClick={() => removeArrayItem('education', index)}>Remove Education</button>
            )}
          </div>
        ))}
        <button type="button" className="add-btn" onClick={() => addArrayItem('education', { degree: '', institution: '', location: '', start_year: '', end_year: '', grade: '' })}>+ Add Education</button>
      </div>

      {/* 4. Work Experience */}
      <div className="form-section repeatable-section">
        <h3 className="section-title">Work Experience</h3>
        {formData.experience.map((exp, index) => (
          <div key={`${prefix}-exp-${index}`} className="repeatable-item">
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Role *</label>
                  <input type="text" className="field-input" value={exp.role} onChange={e => handleArrayChange('experience', index, 'role', e.target.value)} />
                  {errors[`exp_role_${index}`] && <span className="field-error">{errors[`exp_role_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Company *</label>
                  <input type="text" className="field-input" value={exp.company} onChange={e => handleArrayChange('experience', index, 'company', e.target.value)} />
                  {errors[`exp_company_${index}`] && <span className="field-error">{errors[`exp_company_${index}`]}</span>}
                </div>
              </div>
            </div>
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Start Date *</label>
                  <input type="text" className="field-input" value={exp.start_date} onChange={e => handleArrayChange('experience', index, 'start_date', e.target.value)} />
                  {errors[`exp_start_${index}`] && <span className="field-error">{errors[`exp_start_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">End Date *</label>
                  <input type="text" className="field-input" value={exp.end_date} onChange={e => handleArrayChange('experience', index, 'end_date', e.target.value)} />
                  {errors[`exp_end_${index}`] && <span className="field-error">{errors[`exp_end_${index}`]}</span>}
                </div>
              </div>
            </div>
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Location</label>
                  <input type="text" className="field-input" value={exp.location} onChange={e => handleArrayChange('experience', index, 'location', e.target.value)} />
                </div>
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Responsibilities *</label>
              <textarea className="field-textarea" value={exp.responsibilities} onChange={e => handleArrayChange('experience', index, 'responsibilities', e.target.value)} />
              {errors[`exp_resp_${index}`] && <span className="field-error">{errors[`exp_resp_${index}`]}</span>}
            </div>
            <button type="button" className="remove-btn" onClick={() => removeArrayItem('experience', index)}>Remove Experience</button>
          </div>
        ))}
        <button type="button" className="add-btn" onClick={() => addArrayItem('experience', { role: '', company: '', location: '', start_date: '', end_date: '', responsibilities: '' })}>+ Add Experience</button>
      </div>

      {/* 5. Projects */}
      <div className="form-section repeatable-section">
        <h3 className="section-title">Projects *</h3>
        {formData.projects.map((proj, index) => (
          <div key={`${prefix}-proj-${index}`} className="repeatable-item">
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Title *</label>
                  <input type="text" className="field-input" value={proj.title} onChange={e => handleArrayChange('projects', index, 'title', e.target.value)} />
                  {errors[`proj_title_${index}`] && <span className="field-error">{errors[`proj_title_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Link</label>
                  <input type="text" className="field-input" value={proj.link} onChange={e => handleArrayChange('projects', index, 'link', e.target.value)} />
                </div>
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Tech Stack (comma separated) *</label>
              <input type="text" className="field-input" value={proj.tech_stack} onChange={e => handleArrayChange('projects', index, 'tech_stack', e.target.value)} />
              {errors[`proj_tech_${index}`] && <span className="field-error">{errors[`proj_tech_${index}`]}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Description *</label>
              <textarea className="field-textarea" value={proj.description} onChange={e => handleArrayChange('projects', index, 'description', e.target.value)} />
              {errors[`proj_desc_${index}`] && <span className="field-error">{errors[`proj_desc_${index}`]}</span>}
            </div>
            {formData.projects.length > 1 && (
              <button type="button" className="remove-btn" onClick={() => removeArrayItem('projects', index)}>Remove Project</button>
            )}
          </div>
        ))}
        <button type="button" className="add-btn" onClick={() => addArrayItem('projects', { title: '', description: '', tech_stack: '', link: '' })}>+ Add Project</button>
      </div>

      {/* 6. Certifications */}
      <div className="form-section repeatable-section">
        <h3 className="section-title">Certifications</h3>
        {formData.certifications.map((cert, index) => (
          <div key={`${prefix}-cert-${index}`} className="repeatable-item">
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Name *</label>
                  <input type="text" className="field-input" value={cert.name} onChange={e => handleArrayChange('certifications', index, 'name', e.target.value)} />
                  {errors[`cert_name_${index}`] && <span className="field-error">{errors[`cert_name_${index}`]}</span>}
                </div>
              </div>
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Issuer</label>
                  <input type="text" className="field-input" value={cert.issuer} onChange={e => handleArrayChange('certifications', index, 'issuer', e.target.value)} />
                </div>
              </div>
            </div>
            <div className="form-row">
              <div className="form-col">
                <div className="field-group">
                  <label className="field-label">Date</label>
                  <input type="text" className="field-input" value={cert.date} onChange={e => handleArrayChange('certifications', index, 'date', e.target.value)} />
                </div>
              </div>
            </div>
            <button type="button" className="remove-btn" onClick={() => removeArrayItem('certifications', index)}>Remove Certification</button>
          </div>
        ))}
        <button type="button" className="add-btn" onClick={() => addArrayItem('certifications', { name: '', issuer: '', date: '' })}>+ Add Certification</button>
      </div>

      {/* 7. Achievements */}
      <div className="form-section">
        <h3 className="section-title">Achievements</h3>
        <p className="form-hint">Enter achievements, one per line.</p>
        <div className="field-group">
          <textarea className="field-textarea" value={formData.achievements} onChange={e => handleChange('achievements', e.target.value)} rows={4} />
        </div>
      </div>
    </div>
  );
};

export default ResumeForm;
