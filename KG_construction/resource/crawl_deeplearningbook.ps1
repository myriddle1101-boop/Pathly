param(
  [string]$StartUrl = "https://www.deeplearningbook.org/",
  [string]$OutDir = "D:\ic\master project\project_code\KG_construction\resource"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$domain = "www.deeplearningbook.org"
$pdfDir = Join-Path $OutDir "pdf"
New-Item -ItemType Directory -Force -Path $pdfDir | Out-Null

function Normalize-Url([string]$base, [string]$href) {
  if ([string]::IsNullOrWhiteSpace($href)) { return $null }
  $href = $href.Trim()
  if ($href.StartsWith("#") -or $href.StartsWith("mailto:") -or $href.StartsWith("javascript:") -or $href.StartsWith("tel:")) { return $null }
  try {
    $u = New-Object System.Uri ((New-Object System.Uri $base), $href)
    $b = New-Object System.UriBuilder $u
    $b.Fragment = ""
    return $b.Uri.AbsoluteUri
  } catch { return $null }
}

function Safe-Name([string]$url, [string]$fallbackExt) {
  $u = New-Object System.Uri $url
  $leaf = [System.IO.Path]::GetFileName($u.AbsolutePath)
  if ([string]::IsNullOrWhiteSpace($leaf)) { $leaf = "index$fallbackExt" }
  $leaf = [System.Net.WebUtility]::UrlDecode($leaf)
  $invalid = [System.IO.Path]::GetInvalidFileNameChars()
  foreach ($c in $invalid) { $leaf = $leaf.Replace($c, '_') }
  if (-not [System.IO.Path]::GetExtension($leaf) -and $fallbackExt) { $leaf += $fallbackExt }
  return $leaf
}

$client = New-Object System.Net.WebClient
$client.Headers.Add("User-Agent", "Mozilla/5.0 Codex academic-resource-crawler")
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

$queue = New-Object 'System.Collections.Generic.Queue[string]'
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$pdfSeen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$pages = New-Object System.Collections.Generic.List[object]
$pdfs = New-Object System.Collections.Generic.List[object]
$edges = New-Object System.Collections.Generic.List[object]

$queue.Enqueue($StartUrl)
$maxPages = 500
$linkPattern = '(?is)<a\s+[^>]*href\s*=\s*(["''])(.*?)\1'

while ($queue.Count -gt 0 -and $seen.Count -lt $maxPages) {
  $url = $queue.Dequeue()
  if (-not $seen.Add($url)) { continue }
  try {
    $bytes = $client.DownloadData($url)
    $contentType = $client.ResponseHeaders["Content-Type"]
    if (-not $contentType) { $contentType = "" }
    if ($contentType.Contains("application/pdf") -or $url.ToLowerInvariant().Contains(".pdf")) {
      if ($pdfSeen.Add($url)) {
        $name = Safe-Name $url ".pdf"
        $path = Join-Path $pdfDir $name
        $i = 1
        while (Test-Path -Path $path) {
          $stem = [System.IO.Path]::GetFileNameWithoutExtension($name)
          $ext = [System.IO.Path]::GetExtension($name)
          $path = Join-Path $pdfDir ("{0}_{1}{2}" -f $stem,$i,$ext)
          $i++
        }
        [System.IO.File]::WriteAllBytes($path, $bytes)
        $pdfs.Add([pscustomobject]@{ url=$url; local_file=$path; status="downloaded" })
      }
      continue
    }
    if (-not $contentType.Contains("text/html")) {
      $pages.Add([pscustomobject]@{ url=$url; status=200; title=""; content_type=$contentType; local_file=""; note="non-html" })
      continue
    }
    $html = [System.Text.Encoding]::UTF8.GetString($bytes)
    $title = ""
    if ($html -match "(?is)<title[^>]*>(.*?)</title>") { $title = ([System.Net.WebUtility]::HtmlDecode($matches[1]) -replace "\s+", " ").Trim() }
    $pages.Add([pscustomobject]@{ url=$url; status=200; title=$title; content_type=$contentType; local_file=""; note="html" })

    $linkMatches = [regex]::Matches($html, $linkPattern)
    foreach ($m in $linkMatches) {
      $href = $m.Groups[2].Value
      $next = Normalize-Url $url $href
      if (-not $next) { continue }
      $nextUri = New-Object System.Uri $next
      $isPdf = $nextUri.AbsolutePath.ToLowerInvariant().EndsWith(".pdf")
      if ($isPdf) {
        $edges.Add([pscustomobject]@{ from=$url; to=$next; kind="pdf" })
        if ($pdfSeen.Add($next)) {
          try {
            $pdfBytes = $client.DownloadData($next)
            $name = Safe-Name $next ".pdf"
            $path = Join-Path $pdfDir $name
            $i = 1
            while (Test-Path -Path $path) {
              $stem = [System.IO.Path]::GetFileNameWithoutExtension($name)
              $ext = [System.IO.Path]::GetExtension($name)
              $path = Join-Path $pdfDir ("{0}_{1}{2}" -f $stem,$i,$ext)
              $i++
            }
            [System.IO.File]::WriteAllBytes($path, $pdfBytes)
            $pdfs.Add([pscustomobject]@{ url=$next; local_file=$path; status="downloaded" })
          } catch {
            $pdfs.Add([pscustomobject]@{ url=$next; local_file=""; status=("error: " + $_.Exception.Message) })
          }
        }
      } elseif ($nextUri.Host -ieq $domain) {
        $edges.Add([pscustomobject]@{ from=$url; to=$next; kind="html" })
        if (-not $seen.Contains($next)) { $queue.Enqueue($next) }
      } else {
        $edges.Add([pscustomobject]@{ from=$url; to=$next; kind="external" })
      }
    }
  } catch {
    $pages.Add([pscustomobject]@{ url=$url; status=0; title=""; content_type=""; local_file=""; note=("error: " + $_.Exception.Message) })
  }
}

$pagesPath = Join-Path $OutDir "deeplearningbook_pages.csv"
$pdfsPath = Join-Path $OutDir "deeplearningbook_pdfs.csv"
$edgesPath = Join-Path $OutDir "deeplearningbook_links.csv"
$mdPath = Join-Path $OutDir "deeplearningbook_index.md"

$pages | Sort-Object url | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $pagesPath
$pdfs | Sort-Object url | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $pdfsPath
$edges | Sort-Object from,to | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $edgesPath

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Deep Learning Book crawl index")
$lines.Add("")
$lines.Add("Start URL: $StartUrl")
$lines.Add("Crawled at: $((Get-Date).ToString('s'))")
$lines.Add("")
$lines.Add("## Summary")
$lines.Add("")
$lines.Add("- HTML/pages crawled: $($pages.Count)")
$lines.Add("- PDFs found: $($pdfs.Count)")
$lines.Add("- Link edges recorded: $($edges.Count)")
$lines.Add("")
$lines.Add("## Downloaded PDFs")
$lines.Add("")
if ($pdfs.Count -eq 0) { $lines.Add("No public PDF files were found during the crawl.") } else { foreach ($p in ($pdfs | Sort-Object url)) { $lines.Add("- [$($p.url)]($($p.url)) -> `$($p.local_file)` [$($p.status)]") } }
$lines.Add("")
$lines.Add("## Crawled Pages")
$lines.Add("")
foreach ($p in ($pages | Sort-Object url)) { $label = if ($p.title) { $p.title } else { $p.url }; $lines.Add("- [$label]($($p.url))") }
[System.IO.File]::WriteAllLines($mdPath, $lines, (New-Object System.Text.UTF8Encoding $false))

[pscustomobject]@{
  pages = $pages.Count
  pdfs = $pdfs.Count
  links = $edges.Count
  out_dir = $OutDir
  pages_csv = $pagesPath
  pdfs_csv = $pdfsPath
  links_csv = $edgesPath
  index_md = $mdPath
} | ConvertTo-Json -Depth 4
