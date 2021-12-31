library(tidyverse)
library(glue)

childes_dir <- "~/childes/phonbank"
data_dir <- "data"

# w_files <- dir(childes_dir, "w.csv", recursive = TRUE)
# mor_files <- dir(childes_dir, "mor.csv", recursive = TRUE)
# mk_files <- dir(childes_dir, "mk.csv", recursive = TRUE)

read_childes_files <- function(path, files) {
  map(files, function(f) {
    suppressWarnings(suppressMessages({
      read_csv(file.path(path, f)) |> mutate(file = f) |> select(-X1)
    }))
  })
}

# w <- read_childes_files(w_files)
# mor <- read_childes_files(mor_files)
# mk <- read_childes_files(mk_files)

# w_comb <- w |>
#   keep(\(wd) ncol(wd) > 2) |>
#   map_df(\(wd) wd |> mutate(replacement = as.character(replacement))) |>
#   mutate(across(where(is.double), as.integer))
# saveRDS(w_comb, "Biling_w.rds")
# mor_comb <- mor |> bind_rows() |> mutate(across(where(is.double), as.integer))
# mk_comb <- mk |> bind_rows() |> mutate(across(where(is.double), as.integer))

# saveRDS(mor_comb, "mor_comb.rds")

# rm(w)
# rm(mor)
# rm(mk)

combine_collection <- function(coll) {
  message(glue("Processing collection {coll}..."))
  coll_path <- file.path(childes_dir, coll)
  coll_data_path <- file.path(data_dir, coll)
  if (!dir.exists(coll_data_path)) dir.create(coll_data_path)
  
  message("  Processing w...")
  w_files <- dir(coll_path, "w.csv", recursive = TRUE)
  w <- read_childes_files(coll_path, w_files)
  w_comb <- w |>
    keep(\(wd) ncol(wd) > 2) |>
    map_df(\(wd) wd |> mutate(replacement = as.character(replacement))) |>
    mutate(across(where(is.double), as.integer))
  rm(w)
  saveRDS(w_comb, file.path(coll_data_path, "w.rds"))
  
  message("  Processing mor...")
  mor_files <- dir(coll_path, "mor.csv", recursive = TRUE)
  mor <- read_childes_files(coll_path, mor_files)
  mor_comb <- mor |> bind_rows() |> mutate(across(where(is.double), as.integer))
  rm(mor)
  saveRDS(mor_comb, file.path(coll_data_path, "mor.rds"))
  
  message("  Processing mk...")
  mk_files <- dir(coll_path, "mk.csv", recursive = TRUE)
  mk <- read_childes_files(coll_path, mk_files)
  mk_comb <- mk |> bind_rows() |> mutate(across(where(is.double), as.integer))
  rm(mk)
  saveRDS(mk_comb, file.path(coll_data_path, "mk.rds"))
}

walk(dir(childes_dir), combine_collection)


mor_gra <- mor_comb |>
  group_by(transcript, u_fk) |>
  mutate(compound_first = is_compound &
           (row_number() == 1 | is.na(lag(w_fk)) | w_fk != lag(w_fk) | lag(is_separated_prefix)),
         counted = !is.na(gra_index) & (!is_compound | compound_first),
         gra_fake = cumsum(counted)) |>
  ungroup()

mor_gra |> filter(is.na(w_fk)) |> count(pos)
mor_gra |> filter(is.na(counted))
mor_gra |> filter(gra_index != gra_fake)

mor_gra |> filter(pos == "v:exist", is.na(w_fk)) |> pull(transcript)
mor_gra |> filter(str_detect(transcript, "Yamaguchi/030514"), u_fk == 256) |> View()

mor_gra |>
  group_by(transcript, u_fk) |>
  filter(any(gra_index != gra_fake), !any(str_detect(stem, "_"))) |> View()

# TODO: gra_fake for w_fk 1577 should all be 6 (doesn't increment because of first mor not being a compound)
# mor_gra |> filter(u_fk == 424, str_detect(transcript, "020912")) |>
#   select(is_compound, is_separated_prefix, compound_first, counted, w_fk,
#          pos, stem, english, starts_with("gra"))
# w_comb |> filter(u_fk == 424, str_detect(transcript, "020912"))

mor_head_check <- mor_comb |>
  select(transcript, u_fk, w_fk, pos, stem, contains("gra")) |>
  group_by(transcript, u_fk) |>
  mutate(before = gra_head == 0, after = max(gra_index) + 1,
         good_index = before | after | gra_head %in% gra_index) |>
  filter(!all(good_index)) |>
  ungroup()
mor_head_check
