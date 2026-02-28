-- Create evidence storage bucket (private)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'evidence',
  'evidence',
  false,
  52428800,
  ARRAY['image/png', 'image/jpeg', 'application/json']
)
ON CONFLICT (id) DO NOTHING;

-- Authenticated users and service role can read/write evidence
CREATE POLICY "Authenticated can read evidence"
ON storage.objects FOR SELECT
USING (bucket_id = 'evidence' AND (auth.role() = 'authenticated' OR auth.role() = 'service_role'));

CREATE POLICY "Authenticated can insert evidence"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'evidence' AND (auth.role() = 'authenticated' OR auth.role() = 'service_role'));
