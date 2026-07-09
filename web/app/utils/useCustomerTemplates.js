'use client';

import { useState } from 'react';
import { saveConfig } from './config';

// Shared customer-template management (save/select/delete), used by page.js,
// provision/page.js, and credit-note/page.js. Each page keeps its customer
// fields as separate useState hooks (not one object), so the caller supplies
// getFields()/applyTemplate() adapters instead of a single field-state object.
export function useCustomerTemplates({ config, setConfig, templatesKey, getFields, applyTemplate, setToast }) {
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const templates = config[templatesKey] || {};
  const templateNames = Object.keys(templates);

  const onTemplateSelect = (name) => {
    setSelectedTemplate(name);
    applyTemplate(templates[name] || {});
  };

  const saveTemplate = () => {
    const fields = getFields();
    const name = prompt('Name für diese Vorlage:', fields.name?.trim() || '');
    if (!name?.trim()) return;
    const newTemplates = { ...templates, [name.trim()]: fields };
    const newCfg = { ...config, [templatesKey]: newTemplates };
    setConfig(newCfg);
    saveConfig(newCfg);
    setSelectedTemplate(name.trim());
    setToast({ text: `💾 Vorlage '${name.trim()}' gespeichert`, type: 'success' });
  };

  const deleteTemplate = () => {
    if (!selectedTemplate) return;
    if (!confirm(`Vorlage '${selectedTemplate}' wirklich löschen?`)) return;
    const newTemplates = { ...templates };
    delete newTemplates[selectedTemplate];
    const newCfg = { ...config, [templatesKey]: newTemplates };
    setConfig(newCfg);
    saveConfig(newCfg);
    setSelectedTemplate('');
    setToast({ text: `🗑 Vorlage gelöscht`, type: 'success' });
  };

  return { templates, templateNames, selectedTemplate, onTemplateSelect, saveTemplate, deleteTemplate };
}
