library(xml2)
library(tidyverse)

talkbank_xsd <- read_xml("talkbank.xsd")
elements <- xml_find_all(talkbank_xsd, "xs:element")
element_names <- xml_attr(elements, "name")
element_docs <- xml_text(xml_find_first(elements, ".//xs:documentation"))
# element_refs <- xml_attr(elements, "ref")
# element_types <- xml_find_first(elements, ".//xs:attribute[@name='type']")
# xml_find_all(element_types, "xs:enumeration")
xml_find_all(elements, "//xs:element[@name='c']")
xml_find_all(elements, "//xs:element[@name='mk']//xs:enumeration")
xml_find_all(elements, "//xs:element[@name='mk']//xs:attribute[@name='type']//xs:enumeration")
xml_find_all(elements, "//xs:attribute[@name='type']//xs:enumeration")
# xml_attr(element_types, "type")

fields <- tibble(name = element_names, doc = str_trim(element_docs))

reader <- read_file("~/Dropbox/projects/childes/childes-db/djangoapp/db/childes.py")

fields %>%
  mutate(in_reader = str_detect(reader, paste0("\\{\\%s\\}", name))) %>%
  write_csv("talkbank_fields.csv")
  